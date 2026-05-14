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
    }
}
