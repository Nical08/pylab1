from flask_sqlalchemy import SQLAlchemy

# Istanza unica di SQLAlchemy condivisa da tutta l'app.
# Va importata da qui (non creata altrove) per evitare database separati.
db = SQLAlchemy()
