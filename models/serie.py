from extensions import db


class Serie(db.Model):
    __tablename__ = "series"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    temporadas = db.Column(db.Integer, nullable=False)

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
        backref=db.backref("series", lazy=True),
    )