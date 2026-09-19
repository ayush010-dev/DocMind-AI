import os
import time
import requests

API_URL = "http://127.0.0.1:8000"

def wait_for_ready(doc_id):
    print(f"Waiting for document {doc_id} to be ready...")
    for _ in range(60): # 1 minute timeout
        res = requests.get(f"{API_URL}/documents/{doc_id}/status", proxies={"http": None, "https": None})
        if res.status_code == 200:
            status = res.json().get("status")
            if status == "ready":
                print("Document processing complete!")
                return True
            elif status == "failed":
                print("Document processing failed:", res.json().get("error_message"))
                return False
        time.sleep(2)
    print("Timeout waiting for document.")
    return False

def chat(doc_ids, chat_id, query):
    print(f"\nQ: {query}")
    res = requests.post(f"{API_URL}/chat", json={
        "question": query,
        "document_ids": doc_ids,
        "chat_id": chat_id
    }, proxies={"http": None, "https": None})
    
    if res.status_code == 200:
        data = res.json()
        print(f"A: {data['answer']}")
        return data['chat_id']
    else:
        print(f"Error: {res.status_code} - {res.text}")
        return chat_id

if __name__ == "__main__":
    test_pdf = os.path.join(os.path.dirname(__file__), "..", "uploads", "test_doc.txt")
    if not os.path.exists(test_pdf):
        with open(test_pdf, "w", encoding="utf-8") as f:
            f.write("Piyush with address B3/137 has serial number 698.\nAyush is his brother.\nTotal Electors = 716.\n")
            
    with open(test_pdf, "rb") as f:
        for _ in range(10):
            try:
                res = requests.post(f"{API_URL}/upload", files={"file": f}, proxies={"http": None, "https": None})
                break
            except requests.exceptions.ConnectionError:
                print("Server not ready, retrying in 2 seconds...")
                time.sleep(2)
        else:
            print("Failed to connect to server.")
            exit(1)
        data = res.json()
        doc_id = data["document_id"]
        chat_id = data["chat_id"]
        print(f"Uploaded successfully. Doc ID: {doc_id}, Chat ID: {chat_id}")
        
        if wait_for_ready(doc_id):
            chat_id = chat([doc_id], chat_id, "Is there anyone named Piyush?")
            chat_id = chat([doc_id], chat_id, "What is Piyush's serial number?")
            chat_id = chat([doc_id], chat_id, "What is the total number of electors?")
            chat_id = chat([doc_id], chat_id, "What is Piyush's address?")
        else:
            print("Upload failed or processing failed.")
