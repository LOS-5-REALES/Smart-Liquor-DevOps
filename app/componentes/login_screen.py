# app/componentes/login_screen.py
import flet as ft
import asyncio
from auth import login

def build_login_screen(page: ft.Page, on_login_exitoso):
    """
    Construye la pantalla de login.

    Parametros:
        page             -- objeto Page de Flet
        on_login_exitoso -- funcion async que se llama cuando el login es correcto

    Retorna ft.Container con la pantalla completa.
    """
    inp_email    = ft.TextField(
        label="Correo electronico",
        width=320,
        prefix_icon="email",
        keyboard_type=ft.KeyboardType.EMAIL,
        autofocus=True,
    )
    inp_password = ft.TextField(
        label="Contrasena",
        width=320,
        prefix_icon="lock",
        password=True,
        can_reveal_password=True,
    )
    txt_error    = ft.Text("", color="red", size=13)
    btn_login    = ft.ElevatedButton(
        "Ingresar",
        width=320,
        height=45,
        bgcolor="#1F4E79",
        color="white",
        icon="login",
    )
    progress     = ft.ProgressBar(width=320, visible=False, color="amber")

    async def intentar_login(e=None):
        txt_error.value  = ""
        email    = inp_email.value.strip()
        password = inp_password.value.strip()

        if not email or not password:
            txt_error.value = "Completa todos los campos."
            await page.update_async()
            return

        # Mostrar progreso
        btn_login.disabled = True
        progress.visible   = True
        await page.update_async()

        try:
            
            usuario = login(email, password)
            if usuario:
                import asyncio
                asyncio.ensure_future(on_login_exitoso(usuario))
        except Exception as ex:
            msg = str(ex)
            if "Invalid login credentials" in msg:
                txt_error.value = "Correo o contrasena incorrectos."
            elif "Email not confirmed" in msg:
                txt_error.value = "Debes confirmar tu correo primero."
            else:
                txt_error.value = f"Error: {msg}"
        finally:
            btn_login.disabled = False
            progress.visible   = False
            await page.update_async()

    btn_login.on_click          = intentar_login
    inp_password.on_submit      = intentar_login
    inp_email.on_submit = lambda e: asyncio.ensure_future(intentar_login(e))


    return ft.Container(
        expand=True,
        bgcolor="#0b0d0f",
        content=ft.Column(
            alignment="center",
            horizontal_alignment="center",
            expand=True,
            controls=[
                # Logo / titulo
                ft.Icon("local_bar", size=64, color="amber"),
                ft.Text(
                    "Smart-Liquor",
                    size=32, weight="bold", color="white"
                ),
                ft.Text(
                    "Panel Administrativo",
                    size=14, color="grey"
                ),
                ft.Divider(height=30, color="transparent"),

                # Formulario
                inp_email,
                ft.Container(height=8),
                inp_password,
                ft.Container(height=4),
                progress,
                ft.Container(height=4),
                txt_error,
                ft.Container(height=8),
                btn_login,

                ft.Divider(height=20, color="transparent"),
                ft.Text(
                    "Logistica Chincha • Supabase Cloud",
                    size=11, color="#333"
                ),
            ],
        ),
    )