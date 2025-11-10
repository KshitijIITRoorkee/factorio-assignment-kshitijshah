# RUN.md — Commands and Validation

## Quick Start
All commands assume your working directory is `part2_assignment/`.

```bash
# Run both sample cases
python run_samples.py "python factory/main.py" "python belts/main.py"


# Default commands
FACTORY_CMD="python factory/main.py" BELTS_CMD="python belts/main.py" pytest -q

#Manual CLI
#Factory
cat samples/factory_input.json | python factory/main.py > output.json
#Belts
cat samples/belts_input.json | python belts/main.py > output.json

