from extensions import db


class Pelicula(db.Model):
    __tablename__ = "peliculas"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    duracion = db.Column(db.Integer, nullable=False)

    categoria_id = db.Column(
        db.Integer,
        db.ForeignKey("categorias.id"),
        nullable=False,
    )

    fecha_creacion = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
    )

    categoria = db.relationship(
        "Categoria",
        backref=db.backref("peliculas", lazy=True),
    )