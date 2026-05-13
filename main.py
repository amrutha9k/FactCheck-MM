import pandas as pd
import os
import time
import argparse
import logging
from sentence_transformers import SentenceTransformer
from core_pipeline import verify_row, setup_openai 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("batch_process.log"),
        logging.StreamHandler()
    ]
)

def run_batch(input_file, output_file):
    """
    Processes a batch of claims from an Excel file and saves results.
    Supports resuming from an existing output file.
    """
    logging.info("Initializing models and API clients...")
    embed_model = SentenceTransformer('BAAI/bge-m3')
    client = setup_openai()
    
    # 1. Determine whether to resume or start fresh
    if os.path.exists(output_file):
        logging.info(f"Resuming from existing output file: {output_file}")
        df = pd.read_excel(output_file,engine='openpyxl')
    elif os.path.exists(input_file):
        logging.info(f"Starting new process from: {input_file}")
        df = pd.read_excel(input_file,engine='openpyxl')
    else:
        logging.error(f"Error: Input file '{input_file}' not found.")
        return

    # 2. Ensure all output columns exist
    output_cols = [
        'predicted_verdict', 'correction_native', 'correction_english',
        'explanation_native', 'explanation_english', 'claim_english',
        'top_3_article_urls', 'top_3_image_urls'
    ]
    
    for col in output_cols:
        if col not in df.columns:
            df[col] = None 

    total_rows = len(df)
    logging.info(f"Total rows to process: {total_rows}")
        
    # 3. Process each row
    for i, row in df.iterrows():
        # Skip if already processed (for resuming)
        if pd.notna(row['predicted_verdict']) and str(row['predicted_verdict']).strip() != "" and "Error" not in str(row['predicted_verdict']):
            continue

        print(f"\n" + "="*60)
        logging.info(f"PROCESSING ROW {i+1} / {total_rows}")
        print(f"="*60)
        
        try:
            # Respectful API delay
            time.sleep(1) 
            
            # Call the verification logic
            output = verify_row(row, embed_model, client)
            
            # Map output to dataframe
            df.at[i, 'predicted_verdict'] = output.get('verdict')
            df.at[i, 'correction_native'] = output.get('corrected_claim_native')
            df.at[i, 'correction_english'] = output.get('corrected_claim_english')
            df.at[i, 'explanation_native'] = output.get('explanation_native')
            df.at[i, 'explanation_english'] = output.get('explanation_english')
            df.at[i, 'claim_english'] = output.get('claim_english')
            df.at[i, 'top_3_article_urls'] = output.get('top_3_article_urls')
            df.at[i, 'top_3_image_urls'] = output.get('top_3_image_urls')

            logging.info(f"Row {i+1} Success - Verdict: {output.get('verdict')}")

            # Save after every successful row to prevent data loss
            df.to_excel(output_file, index=False)
            
        except Exception as e:
            logging.error(f"Row {i+1} Failed: {str(e)}")
            df.at[i, 'predicted_verdict'] = f"Error: {str(e)}"
            df.to_excel(output_file, index=False)

    logging.info("Batch processing complete.")

if __name__ == "__main__":
    # Command-line argument parsing
    parser = argparse.ArgumentParser(description="Multimodal Fact-Checking Pipeline")
    
    parser.add_argument(
        "--input", 
        type=str, 
        default="input_claims.xlsx", 
        help="Path to the source Excel file."
    )
    
    parser.add_argument(
        "--output", 
        type=str, 
        default="results_final.xlsx", 
        help="Path where the results will be saved."
    )

    args = parser.parse_args()

    # Launch processing
    run_batch(args.input, args.output)


