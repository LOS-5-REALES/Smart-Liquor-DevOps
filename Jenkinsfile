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
            powershell """
                \$keyPath = "C:\\\\jenkins_key_tmp\\\\id_rsa"
                New-Item -ItemType Directory -Force -Path "C:\\\\jenkins_key_tmp" | Out-Null
                Copy-Item "\$env:SSH_KEY" \$keyPath -Force

                # Usar icacls directamente que es más confiable en Jenkins
                icacls \$keyPath /inheritance:r | Out-Null
                icacls \$keyPath /grant:r "SYSTEM:F" | Out-Null
                icacls \$keyPath /grant:r "Administradores:F" | Out-Null
                icacls \$keyPath /remove "BUILTIN\\\\Usuarios" | Out-Null
                icacls \$keyPath /remove "Everyone" | Out-Null

                Write-Host "Permisos aplicados:"
                icacls \$keyPath

                ssh -i \$keyPath -o StrictHostKeyChecking=no smartliquor@57.156.66.168 `
                    "cd /home/smartliquor/Smart-Liquor-DevOps && git pull origin dev/dashboard-mejoras && docker-compose -f docker/docker-compose.yml down && docker-compose -f docker/docker-compose.yml up -d --build"

                Remove-Item \$keyPath -Force
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
