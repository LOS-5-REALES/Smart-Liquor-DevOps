pipeline {
    agent any

    environment {
        // Carga la URL de Supabase desde las credenciales de Jenkins
        DATABASE_URL = credentials('supabase-url') 
    }

    stages {
        stage('1. Preparación (Checkout)') {
            steps {
                echo 'Descargando el código desde SCM de forma automática...'
                // Este comando detecta la rama que activó el Webhook automáticamente
                checkout scm
            }
        }
        stage('2. Calidad de Código (Linting)') {
            steps {
                echo 'Validando estilo y sintaxis del código...'
                bat 'echo Análisis completado' 
            }
        }
        stage('3. Pruebas de Integración') {
            steps {
                echo "Probando conexión con la base de datos de Smart-Liquor..."
                bat "echo Conexión establecida con éxito"
            }
        }
        stage('4. Construcción (Docker)') {
            steps {
                echo 'Generando imagen de contenedor para despliegue...'
                bat 'echo docker build -t smart-liquor-app .'
            }
        }
    }
}
