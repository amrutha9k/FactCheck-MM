import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report

def calculate_metrics(file_path):
    # 1. Load the Excel file
    try:
        df = pd.read_excel(file_path)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return

    # 2. Standardize text (remove spaces, make lowercase to avoid mismatches)
    # This handles 'Fake ', 'fake', 'Fake', etc.
    df['label'] = df['label'].astype(str).str.lower().str.strip()
    df['predicted_verdict'] = df['predicted_verdict'].astype(str).str.lower().str.strip()

    # 3. Create Mapping Dictionaries
    
    # Map 'label' (Ground Truth)
    ground_truth_map = {
        'real': 1,
        'fake': 0
    }

    # Map 'verdict' (Model Prediction)
    # We treat 'misleading' as 0 (Fake) because it is not True.
    prediction_map = {
        'true': 1,
        'True':1,
        'False':0,
        'false': 0,
        'misleading': 0, 
        'Misleading':0,
        'unverified': -1  # We will filter these out later
    }

    # 4. Map the columns to numbers
    df['y_true'] = df['label'].map(ground_truth_map)
    df['y_pred'] = df['predicted_verdict'].map(prediction_map)

    # 5. Data Cleaning
    # Drop rows where 'label' was something unexpected (not real/fake)
    df = df.dropna(subset=['y_true'])
    
    # Handle 'Unverified' or errors in prediction
    initial_count = len(df)
    df = df.dropna(subset=['y_pred'])
    df = df[df['y_pred'] != -1] # Remove unverified if any
    final_count = len(df)

    if initial_count != final_count:
        print(f"Note: {initial_count - final_count} rows were dropped (Unverified or unknown labels).")

    # 6. Calculate Metrics
    y_true = df['y_true']
    y_pred = df['y_pred']

    # Calculate individual scores
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, pos_label=1) # Precision for 'Real' class
    recall = recall_score(y_true, y_pred, pos_label=1)       # Recall for 'Real' class
    f1 = f1_score(y_true, y_pred, pos_label=1)               # F1 for 'Real' class

    # 7. Print Report
    print(f"PERFORMANCE REPORT (N={len(df)})")
    print("-" * 20)
    print(f"Accuracy:  {accuracy:.4f}  ({accuracy*100:.2f}%)")
    print(f"Precision: {precision:.4f} ")
    print(f"Recall:    {recall:.4f} ")
    print(f"F1-Score:  {f1:.4f} ")
   
    
    # Detailed text report
    target_names = ['Fake/Misleading (0)', 'Real (1)']
    print("\nDetailed Classification Report:")
    print(classification_report(y_true, y_pred, target_names=target_names))

    # Confusion Matrix
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    print("\nConfusion Matrix:")
    print(f"True Negatives (Correctly identified Fake): {tn}")
    print(f"False Positives (Fake labeled as Real):     {fp}")
    print(f"False Negatives (Real labeled as Fake):     {fn}")
    print(f"True Positives (Correctly identified Real): {tp}")


# Make sure the file name matches
calculate_metrics('results_final.xlsx')
