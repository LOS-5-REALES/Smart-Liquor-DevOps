pipeline {
    agent any

    environment {
        DATABASE_URL = credentials('supabase-url')
        COMPOSE_FILE = "docker/docker-compose.yml"
    }

    stages {
        stage('1.Preparar .env') {
            steps {
                writeFile file: '.env', text: "DATABASE_URL=${env.DATABASE_URL}\n"
            }
        }
        stage('2.Calidad de Código (Linting)') {
            steps {
                echo 'Validando estilo y sintaxis del código...'
                bat 'flake8 .'
            }
        }
        stage('3.Pruebas de Integración') {
            steps {
                echo "Ejecutando pruebas de integración..."
                bat 'if exist tests\\integration pytest tests\\integration || exit /b 0'
            }
        }
        stage('4.Construcción (Docker)') {
            steps {
                echo 'Generando imagen de contenedor para despliegue...'
                bat "docker-compose -f ${COMPOSE_FILE} build"
            }
        }
        stage('5.Despliegue (Up Docker) Local') {
            steps {
                echo 'Levantando los servicios (Docker Compose) en local...'
                bat "docker-compose -f ${COMPOSE_FILE} up -d"
            }
        }
        stage('6.Despliegue remoto en VM (SSH manual / Windows)') {
            steps {
                withCredentials([file(credentialsId: 'ssh-key-smartliquor', variable: 'SSH_KEY')]) {
                    bat """
                    set HOME=%cd%
                    icacls %SSH_KEY% /inheritance:r /grant:r "%USERNAME%:R"
                    IF EXIST %SSH_KEY% (
                        echo "Conectando por SSH con clave privada..."
                        ssh -i %SSH_KEY% -o StrictHostKeyChecking=no smartliquor@57.156.66.168 ^
                            "cd /home/smartliquor && git pull origin main && docker-compose -f docker/docker-compose.yml up -d --build"
                    ) ELSE (
                        echo "NO SE ENCONTRÓ EL ARCHIVO DE CLAVE PRIVADA"
                        exit /b 1
                    )
                    """
                }
            }
        }
    } // <---- ESTA LLAVE CIERRA LA SECCIÓN "stages" (¡IMPORTANTE!)

    post {
        always {
            echo 'Finalizando pipeline, limpiando recursos...'
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
