import argparse
import sys
import os
from .driver import run_analysis

def main():
    parser = argparse.ArgumentParser(description="Run ATC-138 Functional Recovery Assessment")
    parser.add_argument("input_dir", help="Path to the directory containing input files (e.g., simulated_inputs.json)")
    parser.add_argument("output_dir", help="Path to the directory where outputs will be saved")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility", default=None)
    parser.add_argument("--force_rebuild", action="store_true", help="Flag to force override of simulated_inputs.json and rebuild", default=False)

    args = parser.parse_args()

    # Validate inputs
    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        run_analysis(args.input_dir, args.output_dir, seed=args.seed, force_rebuild=args.force_rebuild)
    except Exception as e:
        print(f"Error running analysis: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
