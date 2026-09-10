# credit_script

The risk team's credit-default training script: `python train.py [--data data/credit.csv]` prepares the data (feature engineering and a stratified split), trains a scaled logistic regression and prints the test accuracy. Nothing is tracked yet. `make_data.py` regenerates `data/credit.csv`.
