# FactCheck-MM: Multilingual Multimodal Live Web Fact-Checking Framework

## Overview

FactCheck-MM is a multilingual multimodal fact-verification framework that performs live web-based evidence retrieval and verification for misinformation detection. The system combines:

* Live web retrieval (Retrieval-Augmented Generation)
* Multilingual semantic query generation
* Multimodal evidence extraction (text + image)
* Semantic evidence ranking using transformer embeddings
* Large Language Model (LLM)-based reasoning
* Source URL/domain exclusion to prevent source contamination
* Cross-lingual fact-checking support

The framework is designed for verifying claims across multiple Indian and global languages using both textual and visual evidence from the web.

---

# Key Features

## Multilingual Fact Verification

Supports multilingual claims including:

* English
* Hindi
* Telugu
* Tamil
* Kannada
* Malayalam
* Bengali
* Gujarati
* Marathi
* Assamese
* Punjabi
* Urdu
* Odia

The framework automatically generates multilingual search queries for improved retrieval quality.

---

## Multimodal Verification

The framework processes:

* Textual claims
* Images associated with claims
* The text evidence retrieved 
* Webpage evidence images and their context

The reasoning module jointly analyzes both textual and visual evidence.

---

## Live Web Retrieval (RAG-Based)

The system retrieves real-time evidence from the web using:

* Google Search via SerpAPI
* Google Custom Search fallback
* Webpage scraping and extraction

Retrieved evidence is dynamically ranked using semantic similarity.

---

## Semantic Evidence Ranking

Uses transformer embeddings for:

* Claim-to-article semantic similarity
* Claim-to-image-context similarity
* Evidence prioritization

Embedding Model:

* BAAI/bge-m3

---

## Advanced Evidence Filtering

Implements several evidence-quality mechanisms:

* Duplicate URL removal
* Source-domain exclusion
* Junk image filtering
* Sidebar/ad image filtering
* Image context extraction
* Metadata-aware image selection
* Semantic image ranking

---

## Source URL Exclusion

The framework excludes the original source domain from retrieval results to avoid contamination and self-reference bias.

Example:

If the claim originates from a specific news article or social media post, retrieval results from the same domain are excluded during evidence gathering.

---

## Structured Reasoning with LLMs

Uses GPT-4o-mini for:

* Evidence aggregation
* Claim verification
* Multilingual explanations
* Corrected factual statements
* Final verdict generation

Possible verdicts:

* True
* False
* Misleading
* Unverified

---

# Framework Architecture

```text
User Claim + Image
                ↓
Multilingual Query Generation
                ↓
Live Web Retrieval
(SerpAPI + Google Search)
                ↓
Webpage Scraping & Content Extraction
(Textual Evidence Extraction)
                ↓
Source URL / Domain Exclusion
(Duplicate & Source Contamination Prevention)
                ↓
Text Processing Pipeline
(Semantic Retrieval + Evidence Ranking)
                ↓
Image Processing Pipeline
(Visual Evidence Extraction + Filtering + Ranking)
                ↓
Multimodal Evidence Aggregation
(Text + Visual Evidence Fusion)
                ↓
LLM-Based Structured Reasoning
                ↓
Verdict Generation
(True / False / Misleading / Unverified)
                ↓
Multilingual Explanation + Corrected Claim
```
---

# Repository Structure

```text
.
├── core_pipeline.py
├── main.py
├── evaluate.py
├── requirements.txt
├── README.md
├── input_claims.xlsx
```

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/amrutha9k/FactCheck-MM
cd FactCheck-MM
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# API Key Setup

The framework requires the following API keys:

* OpenAI API Key
* SerpAPI Key
* Google Custom Search API Key
* Google Custom Search Engine ID (CX)

## Linux / MacOS

```bash
export OPENAI_API_KEY="your_openai_key"
export SERPAPI_KEY="your_serpapi_key"
export GOOGLE_SEARCH_KEY="your_google_search_api_key"
export GOOGLE_CX="your_google_cx_id"
```

---

## Windows (Command Prompt)

```cmd
set OPENAI_API_KEY=your_openai_key
set SERPAPI_KEY=your_serpapi_key
set GOOGLE_SEARCH_KEY=your_google_search_api_key
set GOOGLE_CX=your_google_cx_id
```

---

## Windows (PowerShell)

```powershell
$env:OPENAI_API_KEY="your_openai_key"
$env:SERPAPI_KEY="your_serpapi_key"
$env:GOOGLE_SEARCH_KEY="your_google_search_api_key"
$env:GOOGLE_CX="your_google_cx_id"
```

---

# Input File Format

The framework expects an Excel file named:

```text
input_claims.xlsx
```

Required columns:

| Column Name | Description                         |
| ----------- | ----------------------------------- |
| claim       | User claim text                     |
| url         | Source/origin URL of the claim      |
| image_src   | Image URL associated with the claim |
| label       | Ground-truth label (real/fake)      |

---

# Running the Framework

## Step 1: Place the Input File

Place your dataset in the repository folder as:

```text
input_claims.xlsx
```

---

## Step 2: Run the Pipeline

```bash
python main.py
```

The generated predictions will be saved as:

```text
results_final.xlsx
```

---

# Running Evaluation

```bash
python evaluate.py
```

The evaluation script computes:

* Accuracy
* Precision
* Recall
* F1-score
* Confusion Matrix

---

# Experimental Performance

The framework achieves strong performance on multilingual multimodal fact-verification tasks.

Example Evaluation Metrics:

* Accuracy: 89.58%
* Precision: 93.33%
* Recall: 85.71%
* F1-Score: 89.36%

These results demonstrate the effectiveness of combining:

* multilingual retrieval
* multimodal evidence aggregation
* semantic ranking
* LLM-based reasoning

for misinformation verification.

---

# Output Format

The framework generates the following outputs:

| Column              | Description                        |
| ------------------- | ---------------------------------- |
| predicted_verdict   | Final verification result          |
| correction_native   | Corrected claim in native language |
| correction_english  | Corrected claim in English         |
| explanation_native  | Explanation in native language     |
| explanation_english | Explanation in English             |
| claim_english       | English translation of claim       |
| top_3_article_urls  | Retrieved evidence sources         |
| top_3_image_urls    | Retrieved visual evidence          |

---

# Citation

If you use this framework in research, please cite:

```text
FactCheck-MM: A Multilingual Multimodal Live Web Fact-Checking Framework using Retrieval-Augmented Generation and LLM-based Reasoning.
```

---

# License

This repository is intended for academic and research purposes.
