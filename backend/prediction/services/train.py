"""Training pipeline — trains Random Flood Forest on synthetic data."""

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from prediction.services.synthetic_data import generate_training_data, get_feature_names, get_label_names
from prediction.services.model_loader import save_model


def train_flood_model(test_size=0.2, random_state=42):
    """Train the flood prediction model.

    Args:
        test_size: fraction of data to use for testing
        random_state: random seed for reproducibility

    Returns:
        dict with training results and metrics
    """
    # Generate synthetic data
    print("Generating synthetic training data...")
    X, y = generate_training_data()
    X = np.array(X)
    y = np.array(y)

    print(f"Generated {len(X)} samples")
    print(f"Class distribution: {dict(zip(*np.unique(y, return_counts=True)))}")

    # Split into train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    print(f"Training set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")

    # Train Random Forest
    print("\nTraining Random Forest...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # Evaluate
    print("\nEvaluating model...")
    y_pred = model.predict(X_test)

    label_names = get_label_names()
    target_names = [label_names.get(i, str(i)) for i in sorted(label_names.keys())]

    report = classification_report(y_test, y_pred, target_names=target_names, output_dict=True)
    cm = confusion_matrix(y_test, y_pred)

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=target_names))

    print("Confusion Matrix:")
    print(cm)

    # Feature importance
    feature_names = get_feature_names()
    importances = model.feature_importances_
    top_features = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:10]

    print("\nTop 10 Features:")
    for name, imp in top_features:
        print(f"  {name}: {imp:.4f}")

    # Save model
    print("\nSaving model...")
    model_path = save_model(model, "flood_model.pkl")
    print(f"Model saved to: {model_path}")

    return {
        "model": model,
        "n_samples": len(X),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "top_features": [(name, round(float(imp), 4)) for name, imp in top_features],
        "model_path": model_path,
    }


if __name__ == "__main__":
    train_flood_model()
