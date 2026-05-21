from dotenv import load_dotenv; load_dotenv()
from agents.forecast_engine import _load_all_price_data, build_features, generate_labels, train
import warnings; warnings.filterwarnings('ignore')

print('Loading price data...')
raw = _load_all_price_data()
print(f'Raw rows: {len(raw)}')
print(f'Routes: {list(raw["route"].unique())}')

print()
print('Building features...')
feat = build_features(raw)
print(f'Feature rows (after rolling window filter): {len(feat)}')

print()
print('Generating labels...')
labels = generate_labels(feat)
print(f'Labeled rows: {len(labels)}')
n0 = int((labels == 0).sum())
n1 = int((labels == 1).sum())
print(f'Label distribution: 0={n0}  1={n1}')

if len(labels) >= 50:
    print()
    print('[OK] Sufficient labels. Running train()...')
    result = train()
    print(f'Training complete!')
    print(f'  Model: {result.model_version}')
    print(f'  Samples: {result.n_samples}')
    print(f'  Accuracy: {round(result.accuracy, 3)}')
    print(f'  ROC-AUC: {round(result.roc_auc, 3)}')
    print(f'  F1: {round(result.f1_score, 3)}')
    top = sorted(result.feature_importances.items(), key=lambda x: -x[1])[:5]
    print(f'  Top features: {top}')
else:
    print(f'[!] Only {len(labels)} labels - need 50')
