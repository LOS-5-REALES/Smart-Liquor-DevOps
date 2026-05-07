pipeline {
    agent any

    environment {
        // Asegúrate de que esta credencial exista en Jenkins
        DATABASE_URL = credentials('supabase-url') 
    }

    stages {
        stage('1. Preparación') {
            steps {
                echo 'Descargando código y preparando entorno...'
                checkout scm
                // Instalamos dependencias reales (asumiendo que es Python/Flask por lo de Twilio)
                bat 'pip install -r requirements.txt --user'
            }
        }

        stage('2. Calidad de Código') {
            steps {
                echo 'Ejecutando Linting con Flake8...'
                // Esto verifica errores de sintaxis reales
                bat 'flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics'
            }
        }

        stage('3. Pruebas de Integración') {
            steps {
                echo 'Ejecutando pruebas de conexión y lógica...'
                // Aquí corremos un script de prueba que tú tengas en tu repo
                // Si no tienes uno, podemos crear un test_db.py rápido
                bat 'python -m pytest tests/' 
            }
        }

        stage('4. Construcción Docker') {
            steps {
                echo 'Validando el Dockerfile...'
                // En lugar de un eco, intentamos un build real (si tienes Docker instalado)
                bat 'docker build -t smart-liquor-app:${BRANCH_NAME} .'
            }
        }
    }
    
    post {
        always {
            echo 'Limpiando el espacio de trabajo...'
        }
        failure {
            echo 'El pipeline falló. Notificando al equipo...'
            // Aquí podrías meter el bot de Twilio que mencionaste antes
        }
    }
}
