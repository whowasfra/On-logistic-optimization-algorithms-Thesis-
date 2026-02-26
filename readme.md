# py3dbl - 3D Bin Packing with Load Balancing


A Python library for 3D bin packing with **center of gravity constraints**, developed as part of my thesis on logistics optimization for last-mile delivery.

> **Note:** This library is a fork and extension of [py3dbl](https://github.com/Giulian7/On-logistic-optimization-algorithms-Thesis-), originally developed by Giuliano Pardini (Giulian7). All core architecture and algorithms are based on his work, with additional features and tests added for thesis purposes.

## The Problem

Standard bin packing algorithms (like Left-Bottom-Back) place items greedily starting from one corner. This creates an inherent bias that makes them **incompatible with load balancing constraints** — when you add a center of gravity check, these algorithms reject every placement and fail completely.

## My Contribution

This project extends [py3dbl](https://github.com/Giulian7/On-logistic-optimization-algorithms-Thesis-) with:

1. **Center of Gravity Constraint** — Ensures the load remains balanced within configurable tolerances  
2. **Multi-Anchor Strategy** — A new placement algorithm that generates positions from multiple anchor points (corners, center, symmetric reflections), overcoming the greedy bias

## Results

Tested on a Fiat Ducato cargo van model with asymmetric loads (heavy + light items):

| Strategy | Items Loaded | CoG Deviation |
|----------|--------------|---------------|
| Greedy + CoG constraint | **0/20** | — |
| Multi-Anchor + CoG constraint | **20/20** | < 10% |

The greedy algorithm fails completely with CoG constraints. Multi-Anchor loads everything while keeping the cargo balanced.

## Quick Start

```bash
pip install -r requirements.txt
```

```python
from py3dbl import Packer, BinModel, item_generator, constraints

# Define your vehicle
van = BinModel(name="Ducato", size=(1.67, 2.0, 3.10), max_weight=1400)

# Generate some items
items = item_generator(
    width=(0.15, 0.60), height=(0.15, 0.60), depth=(0.15, 0.80),
    weight=(2, 40), batch_size=50
)

# Pack with load balancing
packer = Packer()
packer.set_default_bin(van)
packer.add_batch(items)
packer.pack(
    strategy="multi_anchor",
    constraints=[
        constraints['weight_within_limit'],
        constraints['fits_inside_bin'],
        constraints['no_overlap'],
        constraints['is_supported'],
        constraints['maintain_center_of_gravity'],  # the key addition
    ]
)

# Visualize
from py3dbl import render_bin_interactive
render_bin_interactive(packer.current_configuration[0])
```

## Run the Comparison Tests

```bash
python test_cog_comparison.py --asymmetric
```

This runs the full comparison between Greedy and Multi-Anchor strategies, with and without CoG constraints. Results are saved as interactive HTML renders in `results/`.

## License

MIT