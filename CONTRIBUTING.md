# Flujo de trabajo

## Ramas

- `main` es la rama estable. Esta protegida: nadie puede pushear directo, todo
  cambio entra por Pull Request con al menos 1 aprobacion.
- Para trabajar en algo nuevo, crea una rama corta desde `main`:
  - `feature/<nombre>` para funcionalidad nueva.
  - `fix/<nombre>` para arreglos de bugs.
  - `chore/<nombre>` para tareas de mantenimiento (CI, dependencias, docs).
- Evita ramas de larga duracion o ramas "backup/" — si necesitas guardar un
  estado, hazlo con un tag o una release, no con una rama paralela.

## Pull Requests

- Abre el PR contra `main` en cuanto tengas algo revisable, no esperes a
  terminar todo.
- Cualquier colaborador listado en `.github/CODEOWNERS` puede revisar y
  aprobar.
- El PR debe pasar lint + tests antes de poder mergear.
- Despues de mergear, borra la rama (GitHub lo ofrece automaticamente).
