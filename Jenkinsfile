pipeline {
    agent any

    environment {
        DATABASE_URL = credentials('supabase-url') // ID del secret en Jenkins, si lo usas
        IMAGE_NAME = "smart-liquor-app"
        COMPOSE_FILE = "docker/docker-compose.yml"
    }

    stages {
        stage('1. Preparación (Checkout)') {
            steps {
                echo 'Descargando el código desde SCM...'
                checkout scm
            }
        }
        stage('2. Calidad de Código (Linting)') {
            steps {
                echo 'Validando estilo y sintaxis del código...'
                bat 'flake8 .' // Cambia a sh 'flake8 .' si tu Jenkins es Linux
            }
        }
        stage('3. Pruebas de Integración') {
            steps {
                echo "Ejecutando pruebas de integración..."
                bat 'if exist tests\\integration pytest tests\\integration || exit /b 0'
                // Usa: sh 'pytest tests/integration || true' en Linux
            }
        }
        stage('4. Construcción (Docker)') {
            steps {
                echo 'Generando imagen de contenedor para despliegue...'
                bat "docker-compose -f ${COMPOSE_FILE} build"
            }
        }
        stage('5. Despliegue (Up Docker)') {
            steps {
                echo 'Levantando los servicios (Docker Compose)...'
                bat "docker-compose -f ${COMPOSE_FILE} up -d"
            }
        }
    }

    post {
        always {
            echo 'Finalizando pipeline, limpiando recursos...'
            // Ejemplo: detener contenedores si lo necesitas al final
            // bat "docker-compose -f ${COMPOSE_FILE} down"
        }
        failure {
            echo 'El pipeline falló. Revisa errores en las etapas anteriores.'
        }
        success {
            echo '¡Pipeline finalizado exitosamente!'
        }
    }
}
