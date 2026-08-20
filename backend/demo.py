import ollama
import tiktoken


# Get encoder for GPT-2 / GPT-4 style BPE
enc = tiktoken.get_encoding("gpt2")

# Encode text into tokens
tokens = enc.encode("Hello world!")
print(tokens)

# Decode back to text
text = enc.decode(tokens)
print(text)
response = ollama.chat(
    model='llama3.2',
    messages=[{'role': 'user', 'content': 'Hello, how are you?'}],
)
print(response['message']['content'])

