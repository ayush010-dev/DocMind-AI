from ai.embedding_generator import generate_embeddings

chunks = [

"Artificial Intelligence is changing the world.",

"Machine Learning is a subset of AI.",

"Deep Learning uses Neural Networks."

]

embeddings = generate_embeddings(chunks)

print(type(embeddings))

print(embeddings.shape)

print(embeddings[0][:10])