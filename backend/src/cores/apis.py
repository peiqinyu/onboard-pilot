from flask import Flask, jsonify, request

app = Flask(__name__)

# Sample data store
books = [
    {"id": 1, "title": "The Hobbit", "author": "J.R.R. Tolkien"},
    {"id": 2, "title": "1849", "author": "George Orwell"}
]

# GET: Retrieve all books
@app.route('/books', methods=['GET'])
def get_books():
    return jsonify(books), 200

# GET: Retrieve a single book by ID
@app.route('/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    book = next((b for b in books if b["id"] == book_id), None)
    if book:
        return jsonify(book), 200
    return jsonify({"error": "Book not found"}), 404


# POST: Add a new book
@app.route('/books', methods=['POST'])
def create_book():
    if not request.json or 'title' not in request.json:
        return jsonify({"error": "Bad request, 'title' is required"}), 400

    new_book = {
        "id": books[-1]["id"] + 1 if books else 1,
        "title": request.json['title'],
        "author": request.json.get('author', 'Unknown')
    }
    books.append(new_book)
    return jsonify(new_book), 201


# PUT: Update an existing book
@app.route('/books/<int:book_id>', methods=['PUT'])
def update_book(book_id):
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        return jsonify({"error": "Book not found"}), 404

    book['title'] = request.json.get('title', book['title'])
    book['author'] = request.json.get('author', book['author'])
    return jsonify(book), 200


# DELETE: Remove a book
@app.route('/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    global books
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        return jsonify({"error": "Book not found"}), 404

    books = [b for b in books if b["id"] != book_id]
    return jsonify({"result": True}), 200


if __name__ == '__main__':
    app.run(debug=True)