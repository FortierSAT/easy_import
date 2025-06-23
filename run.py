from src.web import create_app

app = create_app()
app.secret_key = "dev"  # <-- set the secret on YOUR app

if __name__ == "__main__":
    app.run(debug=True, port=5000)
