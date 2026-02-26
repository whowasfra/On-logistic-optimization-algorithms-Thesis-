#!/usr/bin/env python3
"""
Test di confronto tra strategie di packing per la tesi.

Confronta 4 configurazioni:
1. Greedy (LBB) senza vincolo CoG
2. Greedy (LBB) con vincolo CoG
3. Multi-Anchor senza vincolo CoG
4. Multi-Anchor con vincolo CoG

Metriche valutate:
- Numero di item caricati
- Utilizzo del volume (%)
- Deviazione del centro di gravità dal centro ideale (%)
- Tempo di esecuzione (secondi)
"""

import time
import copy
import os
from decimal import Decimal
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Tuple

import plotly.graph_objects as go

from py3dbl import (
    Bin, BinModel, Packer, Item, Volume, Vector3,
    constraints, item_generator
)
from py3dbl.render import COLORS


# ============================================================================
# CONFIGURAZIONE DEL TEST
# ============================================================================

# Modello di furgone (dimensioni realistiche in metri)
FURGONE = BinModel(
    name="Furgone Ducato L3H2",
    size=(1.67, 2, 3.10),  # Larghezza, Altezza, Profondità
    max_weight=1400  # kg
)

# Parametri per la generazione degli item
ITEM_CONFIG = {
    "width": (0.15, 0.60),      # min-max in metri
    "height": (0.15, 0.60),
    "depth": (0.15, 0.80),
    "weight": (2, 40),          # min-max in kg
    "priority_range": (1, 5),
}

# Numero di item da generare per ogni test
NUM_ITEMS = 50

# Numero di ripetizioni per ogni configurazione (per media statistica)
NUM_RUNS = 5

# Seed per riproducibilità (None per random)
RANDOM_SEED = 42


# ============================================================================
# STRUTTURE DATI
# ============================================================================

@dataclass
class TestResult:
    """Risultato di un singolo test."""
    strategy: str
    with_cog: bool
    items_loaded: int
    items_total: int
    volume_utilization: float  # percentuale
    cog_deviation_x: float     # percentuale rispetto alla larghezza
    cog_deviation_z: float     # percentuale rispetto alla profondità
    execution_time: float      # secondi
    bins_used: int


# ============================================================================
# VINCOLI
# ============================================================================

BASE_CONSTRAINTS = [
    constraints['weight_within_limit'],
    constraints['fits_inside_bin'],
    constraints['no_overlap'],
    constraints['is_supported'],
]

COG_CONSTRAINTS = BASE_CONSTRAINTS + [
    constraints['maintain_center_of_gravity'],
]


# ============================================================================
# FUNZIONI DI UTILITÀ
# ============================================================================

def generate_items(n: int, seed: int = None) -> list[Item]:
    """Genera n item con parametri realistici."""
    if seed is not None:
        import random
        random.seed(seed)
    
    items = item_generator(
        width=ITEM_CONFIG["width"],
        height=ITEM_CONFIG["height"],
        depth=ITEM_CONFIG["depth"],
        weight=ITEM_CONFIG["weight"],
        priority_range=ITEM_CONFIG["priority_range"],
        batch_size=n,
    )
    
    if not isinstance(items, list):
        items = [items]
    
    return items


def generate_asymmetric_items() -> list[Item]:
    """
    Genera un set di item volutamente sbilanciato per sollecitare il vincolo CoG.
    - 5 oggetti pesanti (80 kg ciascuno, 40×40×40 cm)
    - 15 oggetti leggeri (3 kg ciascuno, 50×50×50 cm)
    """
    items = []
    
    # 5 oggetti pesanti
    for i in range(5):
        items.append(Item(
            name=f"Heavy_{i+1}",
            volume=Volume(
                size=Vector3(Decimal('0.40'), Decimal('0.40'), Decimal('0.40')),
                position=Vector3(Decimal(0), Decimal(0), Decimal(0))
            ),
            weight=Decimal('80'),
            priority=1
        ))
    
    # 15 oggetti leggeri
    for i in range(15):
        items.append(Item(
            name=f"Light_{i+1}",
            volume=Volume(
                size=Vector3(Decimal('0.50'), Decimal('0.50'), Decimal('0.50')),
                position=Vector3(Decimal(0), Decimal(0), Decimal(0))
            ),
            weight=Decimal('3'),
            priority=1
        ))
    
    return items


def calculate_items_fingerprint(items: list[Item]) -> tuple[float, float, str]:
    """
    Calcola un fingerprint del set di item per verificare che siano gli stessi.
    Ritorna (volume_totale, peso_totale, hash_breve).
    """
    total_volume = sum(float(item.volume.volume()) for item in items)
    total_weight = sum(float(item.weight) for item in items)
    
    # Hash breve basato sulle dimensioni dei primi 3 item
    dims = []
    for item in items[:3]:
        dims.extend([float(item.width), float(item.height), float(item.depth)])
    hash_str = "-".join(f"{d:.2f}" for d in dims[:6])
    
    return total_volume, total_weight, hash_str


def deep_copy_items(items: list[Item]) -> list[Item]:
    """Crea una copia profonda degli item per riutilizzarli in test diversi."""
    copied = []
    for item in items:
        new_item = Item(
            name=item.name,
            volume=Volume(
                size=Vector3(item.width, item.height, item.depth),
                position=Vector3(Decimal(0), Decimal(0), Decimal(0))
            ),
            weight=item.weight,
            priority=item.priority
        )
        copied.append(new_item)
    return copied


def calculate_cog_deviation(bin) -> tuple[float, float]:
    """
    Calcola la deviazione del CoG dal centro ideale.
    Ritorna (deviazione_x_%, deviazione_z_%).
    """
    if not bin.items:
        return 0.0, 0.0
    
    cog = bin.calculate_center_of_gravity()
    
    # Centro ideale
    center_x = bin.width / Decimal(2)
    center_z = bin.depth / Decimal(2)  # Spostato verso il fondo come nel vincolo
    
    # Deviazione percentuale
    dev_x = abs(float(cog.x - center_x) / float(bin.width)) * 100
    dev_z = abs(float(cog.z - center_z) / float(bin.depth)) * 100
    
    return dev_x, dev_z


def save_bin_render_html(bin, filepath: str, title: str = None):
    """
    Salva il render 3D di un bin come file HTML.
    Renderizza anche bin vuoti mostrando solo il contenitore e il target CoG.
    """
    fig = go.Figure()
    
    # Render degli item (se presenti)
    for idx, item in enumerate(bin.items):
        vol = item.volume
        x, y, z = [float(v) for v in vol.position]
        w, h, d = [float(v) for v in vol.size]
        fig.add_trace(go.Mesh3d(
            x=[x, x+w, x+w, x, x, x+w, x+w, x],
            z=[y, y, y+h, y+h, y, y, y+h, y+h],
            y=[z, z, z, z, z+d, z+d, z+d, z+d],
            color=COLORS[idx % len(COLORS)],
            opacity=0.15,
            name=item.name,
            alphahull=0,
            showscale=False
        ))
    
    # Render del bin (contenitore)
    bvol = Volume(size=bin.dimension)
    x, y, z = 0, 0, 0
    w, h, d = float(bin.width), float(bin.height), float(bin.depth)
    fig.add_trace(go.Mesh3d(
        x=[x, x+w, x+w, x, x, x+w, x+w, x],
        z=[y, y, y+h, y+h, y, y, y+h, y+h],
        y=[z, z, z, z, z+d, z+d, z+d, z+d],
        color="lightgrey",
        opacity=0.05,
        name="Bin",
        alphahull=0,
        showscale=False
    ))
    
    # Centro di gravità attuale (solo se ci sono item)
    if bin.items:
        cog = bin.calculate_center_of_gravity()
        fig.add_trace(go.Scatter3d(
            x=[float(cog.x)],
            y=[float(cog.z)],
            z=[float(cog.y)],
            mode='markers',
            marker=dict(size=15, color='red', symbol='diamond', opacity=1.0),
            name="Center of Gravity"
        ))
    
    # Target CoG
    center_x = float(bin.width) / 2
    center_z = float(bin.depth) / 2
    fig.add_trace(go.Scatter3d(
        x=[center_x],
        y=[center_z],
        z=[0],
        mode='markers',
        marker=dict(size=12, color='orange', symbol='x'),
        name='Target CoG'
    ))
    
    # Viste camera predefinite per screenshot confrontabili
    camera_views = {
        "Angolo": dict(eye=dict(x=1.5, y=1.5, z=1.2), up=dict(x=0, y=0, z=1)),
        "Fronte": dict(eye=dict(x=0, y=-2.0, z=0.5), up=dict(x=0, y=0, z=1)),
        "Dietro": dict(eye=dict(x=0, y=2.0, z=0.5), up=dict(x=0, y=0, z=1)),
        "Lato Sx": dict(eye=dict(x=-2.0, y=0, z=0.5), up=dict(x=0, y=0, z=1)),
        "Lato Dx": dict(eye=dict(x=2.0, y=0, z=0.5), up=dict(x=0, y=0, z=1)),
        "Alto": dict(eye=dict(x=0, y=0, z=2.5), up=dict(x=0, y=1, z=0)),
    }
    
    # Crea bottoni per le viste
    buttons = []
    for view_name, camera in camera_views.items():
        buttons.append(dict(
            label=view_name,
            method="relayout",
            args=[{"scene.camera": camera}]
        ))
    
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Width (X)'),
            zaxis=dict(title='Height (Y)'),
            yaxis=dict(title='Depth (Z)'),
            aspectmode='data',
            camera=camera_views["Angolo"]  # Vista di default
        ),
        showlegend=True,
        title=title or f"3D Packing - {bin} ({len(bin.items)} items)",
        updatemenus=[dict(
            type="buttons",
            direction="right",
            x=0.5,
            y=1.02,
            xanchor="center",
            yanchor="bottom",
            buttons=buttons,
            showactive=True,
            bgcolor="lightgrey",
            bordercolor="black",
            font=dict(size=11)
        )]
    )
    
    fig.write_html(filepath)


def run_single_test(
    items: list[Item],
    strategy: str,
    use_cog_constraint: bool,
    bin_model: BinModel = FURGONE
) -> Tuple[TestResult, Packer]:
    """Esegue un singolo test con la configurazione specificata. Ritorna (result, packer)."""
    
    # Copia gli item per non modificare gli originali
    test_items = deep_copy_items(items)
    
    # Seleziona i vincoli
    active_constraints = COG_CONSTRAINTS if use_cog_constraint else BASE_CONSTRAINTS
    
    # Configura il packer
    packer = Packer()
    packer.set_default_bin(bin_model)
    packer.add_batch(test_items)
    
    # Esegui il packing e misura il tempo
    start_time = time.perf_counter()
    packer.pack(
        constraints=active_constraints,
        strategy=strategy,
        bigger_first=True
    )
    end_time = time.perf_counter()
    
    # Calcola statistiche
    stats = packer.calculate_statistics()
    
    # Conta item caricati
    items_loaded = sum(len(b.items) for b in packer.current_configuration)
    
    # Calcola deviazione CoG (media sui bin)
    total_dev_x, total_dev_z = 0.0, 0.0
    bins_with_items = 0
    for bin in packer.current_configuration:
        if bin.items:
            dev_x, dev_z = calculate_cog_deviation(bin)
            total_dev_x += dev_x
            total_dev_z += dev_z
            bins_with_items += 1
    
    avg_dev_x = total_dev_x / bins_with_items if bins_with_items > 0 else 0.0
    avg_dev_z = total_dev_z / bins_with_items if bins_with_items > 0 else 0.0
    
    return TestResult(
        strategy=strategy,
        with_cog=use_cog_constraint,
        items_loaded=items_loaded,
        items_total=len(items),
        volume_utilization=float(stats['average_volume']) * 100,
        cog_deviation_x=avg_dev_x,
        cog_deviation_z=avg_dev_z,
        execution_time=end_time - start_time,
        bins_used=len(packer.current_configuration)
    ), packer


def run_comparison_tests(
    num_items: int = NUM_ITEMS,
    num_runs: int = NUM_RUNS,
    seed: int = RANDOM_SEED,
    save_renders: bool = True,
    use_asymmetric: bool = False
) -> dict[str, list[TestResult]]:
    """
    Esegue tutti i test di confronto.
    Ritorna un dizionario con i risultati per ogni configurazione.
    """
    
    # Crea cartella results se necessario
    results_dir = Path("results")
    if save_renders:
        results_dir.mkdir(exist_ok=True)
    
    configurations = [
        ("greedy", False, "Greedy senza CoG"),
        ("greedy", True, "Greedy con CoG"),
        ("multi_anchor", False, "Multi-Anchor senza CoG"),
        ("multi_anchor", True, "Multi-Anchor con CoG"),
    ]
    
    results = {name: [] for _, _, name in configurations}
    
    print("=" * 70)
    print("TEST DI CONFRONTO STRATEGIE DI PACKING")
    print("=" * 70)
    
    if use_asymmetric:
        print("Modalità: CARICO ASIMMETRICO (5 pesanti 80kg + 15 leggeri 3kg)")
        num_items = 20  # Override
    else:
        print(f"Item per test: {num_items}")
    
    print(f"Ripetizioni per configurazione: {num_runs}")
    print(f"Bin: {FURGONE.name} ({FURGONE.width}x{FURGONE.height}x{FURGONE.depth}m)")
    print("=" * 70)
    
    for run in range(num_runs):
        # Genera item
        if use_asymmetric:
            items = generate_asymmetric_items()
        else:
            current_seed = seed + run if seed is not None else None
            items = generate_items(num_items, current_seed)
        
        # Calcola fingerprint per confermare che sono gli stessi item per tutte le strategie
        vol_tot, weight_tot, fingerprint = calculate_items_fingerprint(items)
        
        print(f"\n--- Run {run + 1}/{num_runs} ---")
        print(f"    Set di item: vol_tot={vol_tot:.3f}m³, peso_tot={weight_tot:.1f}kg [hash: {fingerprint}]")
        
        for strategy, use_cog, name in configurations:
            result, packer = run_single_test(items, strategy, use_cog)
            results[name].append(result)
            
            # Salva render HTML per ogni bin
            if save_renders:
                if packer.current_configuration:
                    for bin_idx, bin in enumerate(packer.current_configuration):
                        safe_name = name.replace(" ", "_").replace("-", "_")
                        items_count = len(bin.items)
                        filename = f"run{run+1}_{safe_name}_bin{bin_idx}.html"
                        filepath = results_dir / filename
                        title = f"{name} - Run {run+1} - Bin {bin_idx} ({items_count} items)"
                        save_bin_render_html(bin, str(filepath), title)
                else:
                    # Nessun bin creato (es. Greedy con CoG che fallisce) - crea render del bin vuoto
                    empty_bin = Bin(id=0, model=FURGONE)
                    safe_name = name.replace(" ", "_").replace("-", "_")
                    filename = f"run{run+1}_{safe_name}_bin0_empty.html"
                    filepath = results_dir / filename
                    title = f"{name} - Run {run+1} - Bin VUOTO (0 items)"
                    save_bin_render_html(empty_bin, str(filepath), title)
            
            print(f"      {name}: {result.items_loaded}/{result.items_total} items, "
                  f"vol={result.volume_utilization:.1f}%, "
                  f"CoG(X={result.cog_deviation_x:.1f}%, Z={result.cog_deviation_z:.1f}%), "
                  f"bins={result.bins_used}, t={result.execution_time:.3f}s")
    
    if save_renders:
        print(f"\n✅ Render HTML salvati in: {results_dir.absolute()}/")
    
    return results


def print_summary(results: dict[str, list[TestResult]]):
    """Stampa un riepilogo statistico dei risultati."""
    
    print("\n")
    print("=" * 90)
    print("RIEPILOGO STATISTICO (medie)")
    print("=" * 90)
    
    header = f"{'Configurazione':<25} | {'Items':<8} | {'Vol %':<8} | {'CoG X%':<8} | {'CoG Z%':<8} | {'Tempo (s)':<10} | {'Bins':<5}"
    print(header)
    print("-" * 90)
    
    summary_data = []
    
    for name, test_results in results.items():
        n = len(test_results)
        
        avg_items = sum(r.items_loaded for r in test_results) / n
        avg_vol = sum(r.volume_utilization for r in test_results) / n
        avg_cog_x = sum(r.cog_deviation_x for r in test_results) / n
        avg_cog_z = sum(r.cog_deviation_z for r in test_results) / n
        avg_time = sum(r.execution_time for r in test_results) / n
        avg_bins = sum(r.bins_used for r in test_results) / n
        
        total_items = test_results[0].items_total
        
        row = f"{name:<25} | {avg_items:>5.1f}/{total_items:<2} | {avg_vol:>6.1f}% | {avg_cog_x:>6.1f}% | {avg_cog_z:>6.1f}% | {avg_time:>8.4f}s | {avg_bins:>5.1f}"
        print(row)
        
        summary_data.append({
            "name": name,
            "items": avg_items,
            "vol": avg_vol,
            "cog_x": avg_cog_x,
            "cog_z": avg_cog_z,
            "time": avg_time,
            "bins": avg_bins
        })
    
    print("=" * 90)
    
    # Analisi comparativa
    print("\n")
    print("=" * 70)
    print("ANALISI COMPARATIVA")
    print("=" * 70)
    
    # Trova migliori per ogni metrica
    best_items = max(summary_data, key=lambda x: x["items"])
    best_vol = max(summary_data, key=lambda x: x["vol"])
    best_cog = min(summary_data, key=lambda x: x["cog_x"] + x["cog_z"])
    best_time = min(summary_data, key=lambda x: x["time"])
    
    print(f"📦 Più item caricati:      {best_items['name']} ({best_items['items']:.1f} items)")
    print(f"📊 Miglior utilizzo vol:   {best_vol['name']} ({best_vol['vol']:.1f}%)")
    print(f"⚖️  Miglior bilanciamento:  {best_cog['name']} (X={best_cog['cog_x']:.1f}%, Z={best_cog['cog_z']:.1f}%)")
    print(f"⏱️  Più veloce:             {best_time['name']} ({best_time['time']:.4f}s)")
    
    print("=" * 70)
    
    return summary_data


def export_results_csv(results: dict[str, list[TestResult]], filename: str = "results_comparison.csv"):
    """Esporta i risultati in formato CSV per analisi esterne."""
    import csv
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Configurazione", "Run", "Items Caricati", "Items Totali",
            "Utilizzo Volume %", "Deviazione CoG X%", "Deviazione CoG Z%",
            "Tempo (s)", "Bins Usati"
        ])
        
        for name, test_results in results.items():
            for i, r in enumerate(test_results):
                writer.writerow([
                    name, i + 1, r.items_loaded, r.items_total,
                    f"{r.volume_utilization:.2f}", f"{r.cog_deviation_x:.2f}",
                    f"{r.cog_deviation_z:.2f}", f"{r.execution_time:.4f}", r.bins_used
                ])
    
    print(f"\n✅ Risultati esportati in: {filename}")


def export_results_latex(summary_data: list[dict], filename: str = "results_table.tex"):
    """Esporta la tabella riepilogativa in formato LaTeX."""
    
    latex = r"""\begin{table}[h]
\centering
\caption{Confronto tra strategie di packing}
\label{tab:comparison}
\begin{tabular}{l|c|c|c|c|c}
\hline
\textbf{Configurazione} & \textbf{Items} & \textbf{Vol. \%} & \textbf{CoG X\%} & \textbf{CoG Z\%} & \textbf{Tempo (s)} \\
\hline
"""
    
    for data in summary_data:
        name_escaped = data["name"].replace("_", r"\_")
        latex += f"{name_escaped} & {data['items']:.1f} & {data['vol']:.1f} & {data['cog_x']:.1f} & {data['cog_z']:.1f} & {data['time']:.3f} \\\\\n"
    
    latex += r"""\hline
\end{tabular}
\end{table}
"""
    
    with open(filename, 'w') as f:
        f.write(latex)
    
    print(f"✅ Tabella LaTeX esportata in: {filename}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test di confronto strategie di packing")
    parser.add_argument("-n", "--num-items", type=int, default=NUM_ITEMS,
                        help=f"Numero di item da generare (default: {NUM_ITEMS})")
    parser.add_argument("-r", "--runs", type=int, default=NUM_RUNS,
                        help=f"Numero di ripetizioni (default: {NUM_RUNS})")
    parser.add_argument("-s", "--seed", type=int, default=RANDOM_SEED,
                        help=f"Seed per riproducibilità (default: {RANDOM_SEED})")
    parser.add_argument("--export-csv", action="store_true",
                        help="Esporta risultati in CSV")
    parser.add_argument("--export-latex", action="store_true",
                        help="Esporta tabella in LaTeX")
    parser.add_argument("--asymmetric", action="store_true",
                        help="Usa set di item asimmetrico (5 pesanti 80kg + 15 leggeri 3kg)")
    parser.add_argument("--no-renders", action="store_true",
                        help="Non salvare i render HTML dei bin")
    
    args = parser.parse_args()
    
    # Esegui i test
    results = run_comparison_tests(
        num_items=args.num_items,
        num_runs=args.runs,
        seed=args.seed,
        save_renders=not args.no_renders,
        use_asymmetric=args.asymmetric
    )
    
    # Stampa riepilogo
    summary = print_summary(results)
    
    # Esporta se richiesto
    if args.export_csv:
        export_results_csv(results)
    
    if args.export_latex:
        export_results_latex(summary)
