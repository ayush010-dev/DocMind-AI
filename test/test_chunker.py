from ai.text_chunker import chunk_text

sample = "Artificial Intelligence is changing the world. " * 100

chunks = chunk_text(sample)

print("Number of Chunks:", len(chunks))

for i, chunk in enumerate(chunks):
    print(f"\n------ Chunk {i+1} ------")
    print(chunk[:100])  # Sirf pehle 100 characters print karenge