from extensions import db


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(30), default="Usuario")
    token = db.Column(db.String(255), nullable=True)
    token_expira = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )