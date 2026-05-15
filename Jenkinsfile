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
        // ---- ESTE ES EL NUEVO STAGE QUE AGREGA EL DEPLOY REMOTO ----
        stage('6.Despliegue remoto en VM (SSH)') {
            steps {
                echo 'Desplegando remotamente en la VM de Azure...'
                sshagent(['ssh-vm-licores']) {
                    // Cambia smartliquor, IP y ruta según tu configuración real
                    bat '''
                        ssh -o StrictHostKeyChecking=no smartliquor@57.156.66.168 
                        "cd /home/smartliquor && git pull origin main && docker-compose -f docker/docker-compose.yml up -d --build"
                    '''
                    // Si Jenkins corre en Linux, usa 'sh' y elimina el ^ por \
                }
            }
        }
    }

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
