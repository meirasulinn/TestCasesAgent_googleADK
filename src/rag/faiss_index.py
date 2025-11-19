import faiss
import numpy as np

class FaissIndex:
    def __init__(self, dimension):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)

    def add_vectors(self, vectors):
        if not isinstance(vectors, np.ndarray):
            vectors = np.array(vectors, dtype='float32')
        self.index.add(vectors)

    def search(self, query_vector, top_k=5):
        if not isinstance(query_vector, np.ndarray):
            query_vector = np.array([query_vector], dtype='float32')
        distances, indices = self.index.search(query_vector, top_k)
        return distances, indices

# Example usage
if __name__ == "__main__":
    dimension = 128
    faiss_index = FaissIndex(dimension)

    # Add some random vectors
    vectors = np.random.random((10, dimension)).astype('float32')
    faiss_index.add_vectors(vectors)

    # Search for the nearest neighbors
    query_vector = np.random.random(dimension).astype('float32')
    distances, indices = faiss_index.search(query_vector)
    print("Distances:", distances)
    print("Indices:", indices)