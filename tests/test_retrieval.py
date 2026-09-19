import os
import sys

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.intent_classifier import classify_intent_and_resolve_query

def test_intent_classification():
    test_cases = [
        ("Is there anyone named Piyush?", "EXACT_LOOKUP"),
        ("What is Piyush's serial number?", "EXACT_LOOKUP"),
        ("Piyush with address B3/137", "STRUCTURED_LOOKUP"),
        ("Piyush father name Ramesh", "STRUCTURED_LOOKUP"),
        ("How many electors?", "COUNT_AGGREGATION"),
        ("What is the total number of candidates?", "COUNT_AGGREGATION"),
        ("What is written on page 25?", "PAGE_QUERY"),
        ("Summarize this document", "SUMMARY"),
        ("Explain the purpose of this document", "SEMANTIC_QA"),
        ("What is machine learning?", "SEMANTIC_QA")
    ]
    
    passed = 0
    for query, expected_intent in test_cases:
        res = classify_intent_and_resolve_query(query)
        if res["intent"] == expected_intent:
            print(f"Pass: '{query}' -> {expected_intent}")
            passed += 1
        else:
            print(f"Fail: '{query}' -> Expected {expected_intent}, got {res['intent']}")
            
    print(f"\nPassed {passed}/{len(test_cases)} tests.")

if __name__ == "__main__":
    test_intent_classification()
