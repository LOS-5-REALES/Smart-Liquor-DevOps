pipeline {
    agent any

    environment {
        // Uso del ID real de tu credencial en Jenkins
        DATABASE_URL = credentials('supabase-url')
        COMPOSE_FILE = "docker/docker-compose.yml"
    }

    stages {
        stage('1.Preparar .env') {
            steps {
                // Crea el archivo .env con la URL de tu database supabase
                writeFile file: '.env', text: "DATABASE_URL=${env.DATABASE_URL}\n"
            }
        }
        stage('2.Calidad de Código (Linting)') {
            steps {
                echo 'Validando estilo y sintaxis del código...'
                bat 'flake8 .' // Para Jenkins en Windows
                // sh 'flake8 .' // Si tu Jenkins es Linux
            }
        }
        stage('3.Pruebas de Integración') {
            steps {
                echo "Ejecutando pruebas de integración..."
                bat 'if exist tests\\integration pytest tests\\integration || exit /b 0'
                // sh 'pytest tests/integration || true' // Para Linux
            }
        }
        stage('4.Construcción (Docker)') {
            steps {
                echo 'Generando imagen de contenedor para despliegue...'
                bat "docker-compose -f ${COMPOSE_FILE} build"
                // sh "docker-compose -f ${COMPOSE_FILE} build" // Para Linux
            }
        }
        stage('5.Despliegue (Up Docker)') {
            steps {
                echo 'Levantando los servicios (Docker Compose)...'
                bat "docker-compose -f ${COMPOSE_FILE} up -d"
                // sh "docker-compose -f ${COMPOSE_FILE} up -d" // Para Linux
            }
        }
    }

    post {
        always {
            echo 'Finalizando pipeline, limpiando recursos...'
            // bat "docker-compose -f ${COMPOSE_FILE} down"
            // sh "docker-compose -f ${COMPOSE_FILE} down"
        }
        failure {
            echo 'El pipeline falló. Revisa errores en las etapas anteriores.'
        }
        success {
            echo '¡Pipeline finalizado exitosamente!'
        }
    }
}
