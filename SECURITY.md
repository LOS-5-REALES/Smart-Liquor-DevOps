# Manejo de secretos

## Regla

Ninguna credencial (URLs de base de datos con password, tokens, llaves API)
se escribe en texto plano dentro del repositorio. Esto incluye `requirements.txt`,
`docker-compose.yml`, codigo fuente y commits, no solo `.env`.

## Donde vive cada secreto

- **Local / desarrollo**: en `.env` o `.env.local` (ambos en `.gitignore`,
  nunca se commitean). Ver `.env.example` para la forma esperada de la variable,
  sin valores reales.
- **Jenkins**: en *Manage Jenkins → Credentials*, inyectado al pipeline con
  `credentials('supabase-url')`. El `Jenkinsfile` nunca contiene el valor.
- **GitHub**: si en el futuro se agrega un workflow de GitHub Actions, los
  secretos van en *Settings → Secrets and variables → Actions*, no en el
  archivo `.yml`.

## Protecciones automaticas activas en GitHub

- **Secret scanning**: detecta patrones de credenciales conocidas (tokens de
  proveedores) en todo el historial y en cada push nuevo.
- **Push protection**: bloquea un `git push` que intente subir un secreto
  reconocido, antes de que llegue al historial remoto.
- **Dependabot security updates**: abre PR automatico cuando una dependencia
  tiene una vulnerabilidad conocida.

## Que hacer si una credencial se expone igual

1. Rotarla de inmediato en el proveedor (Supabase, Twilio, etc.), no solo
   borrarla del archivo.
2. Reescribir el commit que la expuso solo si el repo todavia no se compartio
   ampliamente; si ya se compartio, asumir que quedo expuesta y priorizar la
   rotacion sobre limpiar el historial.
3. Actualizar la credencial en Jenkins y en los `.env` locales del equipo.
