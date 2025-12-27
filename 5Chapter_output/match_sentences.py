#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to match sentences from English and Chinese JSON files and generate a CSV file.
Includes ALL sentences, even if one language is missing.
"""

import json
import csv
import os
import re


def load_json_file(file_path):
    """Load JSON file and return data."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def split_into_sentences(content, sentence_count):
    """
    Split content into sentences based on sentence_count.
    Returns a list of sentence texts.
    """
    if not content or sentence_count <= 0:
        return []
    
    # Check if content is Chinese or English
    is_chinese = any(ord(c) > 127 for c in content)
    
    # Split by sentence delimiters
    if is_chinese:
        # Chinese sentence delimiters: 。！？
        parts = re.split(r'([。！？])', content)
        sentence_parts = []
        for i in range(0, len(parts) - 1, 2):
            if i + 1 < len(parts):
                sentence_parts.append(parts[i] + parts[i+1])
        if len(parts) % 2 == 1 and parts:
            sentence_parts.append(parts[-1])
    else:
        # English sentence delimiters: . ! ?
        parts = re.split(r'([.!?])', content)
        sentence_parts = []
        for i in range(0, len(parts) - 1, 2):
            if i + 1 < len(parts):
                sentence_parts.append(parts[i] + parts[i+1])
        if len(parts) % 2 == 1 and parts:
            sentence_parts.append(parts[-1])
    
    # Clean up sentences
    sentences = []
    for sent in sentence_parts:
        sent = sent.strip()
        if sent:
            sentences.append(sent)
    
    return sentences


def extract_sentences_from_chapters(chapters):
    """
    Extract all sentences from all chapters.
    Returns a dictionary: {para_id: [sentence_text, ...]}
    """
    sentences_dict = {}
    
    for chapter in chapters:
        paragraphs = chapter.get('paragraphs', [])
        for para in paragraphs:
            para_id = para.get('para_id', '')
            content = para.get('content', '')
            sentence_count = para.get('sentence_count', 0)
            
            if content and para_id:
                # Split content into sentences
                sentences = split_into_sentences(content, sentence_count)
                sentences_dict[para_id] = sentences
    
    return sentences_dict


def match_sentences(english_sentences, chinese_sentences):
    """
    Match English and Chinese sentences by paragraph ID.
    Includes ALL sentences, even if one language is missing.
    Returns a list of tuples: (para_id, sentence_index, english_sentence, chinese_sentence)
    """
    matched = []
    
    # Get all paragraph IDs that exist in either file
    all_para_ids = set(english_sentences.keys()) | set(chinese_sentences.keys())
    
    for para_id in sorted(all_para_ids):
        eng_sents = english_sentences.get(para_id, [])
        chi_sents = chinese_sentences.get(para_id, [])
        
        # Match sentences by index
        max_sentences = max(len(eng_sents), len(chi_sents))
        
        for idx in range(max_sentences):
            eng_sent = ""
            chi_sent = ""
            
            if idx < len(eng_sents):
                eng_sent = eng_sents[idx]
            
            if idx < len(chi_sents):
                chi_sent = chi_sents[idx]
            
            # Include all rows, even if one language is missing
            matched.append((para_id, idx + 1, eng_sent, chi_sent))
    
    return matched


def save_to_csv(matched_sentences, output_path):
    """
    Save matched sentences to CSV file.
    """
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Paragraph ID', 'Sentence Index', 'English Sentence', 'Chinese Sentence'])
        
        for para_id, sent_idx, eng_sent, chi_sent in matched_sentences:
            writer.writerow([para_id, sent_idx, eng_sent, chi_sent])


def main():
    # File paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    english_file = os.path.join(base_dir, 'preprocess_chap1-5.json')
    chinese_file = os.path.join(base_dir, 'preprocess_chap1-5_chinese.json')
    output_file = os.path.join(base_dir, '中英文句子一对一对照表.csv')
    
    print(f"Loading English file: {english_file}")
    english_data = load_json_file(english_file)
    
    print(f"Loading Chinese file: {chinese_file}")
    chinese_data = load_json_file(chinese_file)
    
    # Extract sentences from English file
    print("Extracting sentences from English file...")
    english_chapters = english_data.get('chapters', [])
    english_sentences = extract_sentences_from_chapters(english_chapters)
    print(f"Found {len(english_sentences)} paragraphs in English file")
    
    # Extract sentences from Chinese file
    print("Extracting sentences from Chinese file...")
    chinese_chapters = chinese_data.get('chapters', [])
    chinese_sentences = extract_sentences_from_chapters(chinese_chapters)
    print(f"Found {len(chinese_sentences)} paragraphs in Chinese file")
    
    # Count matching paragraph IDs
    matching_ids = set(english_sentences.keys()) & set(chinese_sentences.keys())
    print(f"Matching paragraph IDs: {len(matching_ids)}")
    print(f"English-only paragraphs: {len(english_sentences) - len(matching_ids)}")
    print(f"Chinese-only paragraphs: {len(chinese_sentences) - len(matching_ids)}")
    
    # Match sentences
    print("Matching sentences...")
    matched = match_sentences(english_sentences, chinese_sentences)
    print(f"Total matched rows: {len(matched)}")
    
    # Count rows with both languages
    both_count = sum(1 for _, _, eng, chi in matched if eng and chi)
    eng_only_count = sum(1 for _, _, eng, chi in matched if eng and not chi)
    chi_only_count = sum(1 for _, _, eng, chi in matched if not eng and chi)
    print(f"  - Both English and Chinese: {both_count}")
    print(f"  - English only: {eng_only_count}")
    print(f"  - Chinese only: {chi_only_count}")
    
    # Save to CSV
    print(f"Saving to CSV file: {output_file}")
    save_to_csv(matched, output_file)
    
    print("Done!")


if __name__ == '__main__':
    main()
