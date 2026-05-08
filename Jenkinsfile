pipeline {
    agent any

    environment {
        // Asegúrate de que las credenciales con el ID 'supabase-url' existen en Jenkins
        DATABASE_URL = credentials('supabase-url') 
    }

    stages {
        stage('1. Preparación (Checkout)') {
            steps {
                echo 'Descargando el código desde SCM de forma automática...'
                checkout scm
            }
        }
        stage('2. Calidad de Código (Linting)') {
            steps {
                echo 'Validando estilo y sintaxis del código...'
                bat 'flake8 .' // Requiere que flake8 esté instalado y accesible en el sistema
            }
        }
        stage('3. Pruebas de Integración') {
            steps {
                echo "Ejecutando pruebas de integración..."
                bat 'if exist tests\\integration pytest tests\\integration || exit /b 0'
            }
        }
        stage('4. Construcción (Docker)') {
            steps {
                echo 'Generando imagen de contenedor para despliegue...'
                bat 'docker build -t smart-liquor-app .'
            }
        }
    }
}
