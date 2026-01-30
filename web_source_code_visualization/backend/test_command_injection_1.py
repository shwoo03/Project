import sys
from pathlib import Path
from test_rule_precision import test_sample, print_results

def main():
    backend_dir = Path(__file__).parent
    rules_path = backend_dir / "rules" / "custom_security.yaml"
    sample_dir = backend_dir.parent / "plob" / "새싹" / "command-injection-1"

    if not sample_dir.exists():
        print(f"Directory not found: {sample_dir}")
        return

    print(f"Testing {sample_dir}...")
    result = test_sample(sample_dir, rules_path)
    if result:
        print_results([result])
    else:
        print("Test failed to run.")

if __name__ == "__main__":
    main()
