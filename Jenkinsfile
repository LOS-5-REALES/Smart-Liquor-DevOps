pipeline {
    agent any
    environment {
        DATABASE_URL = credentials('supabase-url')
        COMPOSE_FILE = "docker/docker-compose.yml"
        VM_IP        = "57.156.66.168"
        VM_USER      = "smartliquor"
        VM_REPO_PATH = "/home/smartliquor/Smart-Liquor-DevOps"
        VM_BRANCH    = "dev/dashboard-mejoras"
        // gcloud se instalo a nivel de usuario en el agente, asi que no esta
        // en el PATH del servicio de Jenkins (corre como cuenta de sistema).
        // Se llama por ruta completa en vez de depender del PATH.
        GCLOUD       = "C:\\Users\\User\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\bin\\gcloud.cmd"
    }

    stages {

        stage('1. Preparar .env') {
            steps {
                writeFile file: '.env', text: "DATABASE_URL=${env.DATABASE_URL}\n"
            }
        }

        stage('2. Instalar dependencias') {
            steps {
                echo 'Instalando dependencias de Python en el agente...'
                bat 'pip install -r requirements.txt'
            }
        }

        stage('3. Calidad de Codigo (Linting)') {
            steps {
                echo 'Validando estilo y sintaxis del codigo...'
                bat 'flake8 .'
            }
        }

        stage('4. Pruebas de Integracion') {
            steps {
                echo "Ejecutando pruebas de integracion..."
                bat 'pytest tests\\integration'
            }
        }

        stage('5. Construccion (Docker)') {
            steps {
                echo 'Generando imagen de contenedor...'
                bat "docker-compose -f ${COMPOSE_FILE} build"
            }
        }

        stage('6. Despliegue Local') {
            steps {
                echo 'Limpiando contenedores previos antes de desplegar...'
                bat "docker-compose -f ${COMPOSE_FILE} down --remove-orphans"
                echo 'Levantando servicios localmente...'
                bat "docker-compose -f ${COMPOSE_FILE} up -d"
            }
        }

        stage('7. Despliegue remoto en VM Azure') {
            steps {
                withCredentials([file(credentialsId: 'ssh-key-smartliquor', variable: 'SSH_KEY')]) {
                    powershell """
                        \$keyPath = "C:\\\\jenkins_key_tmp\\\\id_rsa"
                        New-Item -ItemType Directory -Force -Path "C:\\\\jenkins_key_tmp" | Out-Null
                        Copy-Item "\$env:SSH_KEY" \$keyPath -Force

                        icacls \$keyPath /inheritance:r | Out-Null
                        icacls \$keyPath /grant:r "SYSTEM:F" | Out-Null
                        icacls \$keyPath /grant:r "Administradores:F" | Out-Null
                        icacls \$keyPath /remove "BUILTIN\\\\Usuarios" | Out-Null
                        icacls \$keyPath /remove "Everyone" | Out-Null

                        ssh -i \$keyPath -o StrictHostKeyChecking=no ${VM_USER}@${VM_IP} `
                            "cd ${VM_REPO_PATH} && git pull origin ${VM_BRANCH} && docker-compose -f docker/docker-compose.yml down && docker-compose -f docker/docker-compose.yml up -d --build"

                        Remove-Item \$keyPath -Force
                    """
                }
            }
        }

        stage('8. Despliegue opcional a Cloud Run') {
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
                    withCredentials([file(credentialsId: 'gcp-jenkins-deployer-key', variable: 'GCP_KEY')]) {
                        bat """
                            "%GCLOUD%" auth activate-service-account --key-file="%GCP_KEY%"
                            "%GCLOUD%" config set project smart-liquor-devops
                            "%GCLOUD%" auth configure-docker us-central1-docker.pkg.dev --quiet

                            docker tag docker-app us-central1-docker.pkg.dev/smart-liquor-devops/smart-liquor/app:latest
                            docker tag docker-whatsapp_bot us-central1-docker.pkg.dev/smart-liquor-devops/smart-liquor/whatsapp-bot:latest

                            docker push us-central1-docker.pkg.dev/smart-liquor-devops/smart-liquor/app:latest
                            docker push us-central1-docker.pkg.dev/smart-liquor-devops/smart-liquor/whatsapp-bot:latest

                            "%GCLOUD%" run deploy smart-liquor-app ^
                                --image=us-central1-docker.pkg.dev/smart-liquor-devops/smart-liquor/app:latest ^
                                --region=us-central1 ^
                                --platform=managed ^
                                --allow-unauthenticated ^
                                --port=8000 ^
                                --max-instances=1 ^
                                --set-env-vars=DATABASE_URL=%DATABASE_URL%

                            "%GCLOUD%" run deploy smart-liquor-whatsapp-bot ^
                                --image=us-central1-docker.pkg.dev/smart-liquor-devops/smart-liquor/whatsapp-bot:latest ^
                                --region=us-central1 ^
                                --platform=managed ^
                                --allow-unauthenticated ^
                                --port=8001 ^
                                --max-instances=1 ^
                                --set-env-vars=DATABASE_URL=%DATABASE_URL%
                        """
                    }
                }
            }
        }

        stage('9. Metricas DORA') {
    steps {
        echo 'Calculando metricas DORA...'
        script {
            // Lead Time — tiempo de este pipeline
            def buildStart  = currentBuild.startTimeInMillis
            def buildEnd    = System.currentTimeMillis()
            def leadTimeSeg = (long)((buildEnd - buildStart) / 1000)
            def leadTimeMin = (int)(leadTimeSeg / 60)
            def leadTimeSec = (int)(leadTimeSeg % 60)

            // Numero de build actual como referencia
            def buildNum    = currentBuild.number

            // Sin rawBuild: usamos solo currentBuild que si esta permitido
            // Deployment Frequency: aproximado por numero de build en la semana
            // (1 build por ejecucion del pipeline)
            def deploysUltSemana = buildNum > 7 ? 7 : buildNum

            // Change Failure Rate: calculado del resultado del build actual
            // y los anteriores usando currentBuild.previousBuild
            def totalBuilds  = 0
            def failedBuilds = 0
            def build = currentBuild

            while (build != null && totalBuilds < 20) {
                totalBuilds++
                if (build.result == 'FAILURE') {
                    failedBuilds++
                }
                build = build.previousBuild
            }

            def failureRate = totalBuilds > 0 ? (int)((failedBuilds * 100) / totalBuilds) : 0

            // MTTR: tiempo desde el ultimo fallo hasta este build exitoso
            def mttrMin = 0
            def prev = currentBuild.previousBuild
            if (prev != null && prev.result == 'FAILURE') {
                long diff = (long)((currentBuild.startTimeInMillis - prev.startTimeInMillis) / 1000 / 60)
                mttrMin = (int) diff
            }

            // Nivel DORA
            def nivel = ""
            if (deploysUltSemana >= 7 && failureRate < 15 && leadTimeMin < 15) {
                nivel = "ELITE"
            } else if (deploysUltSemana >= 3 && failureRate < 30 && leadTimeMin < 60) {
                nivel = "HIGH"
            } else if (deploysUltSemana >= 1 && failureRate < 45) {
                nivel = "MEDIUM"
            } else {
                nivel = "LOW"
            }

            echo "========================================"
            echo "   METRICAS DORA - Smart-Liquor"
            echo "========================================"
            echo "  Deployment Frequency (aprox): ${deploysUltSemana} deploys"
            echo "  Lead Time: ${leadTimeMin} min ${leadTimeSec} seg"
            echo "  Change Failure Rate: ${failureRate}% (${failedBuilds}/${totalBuilds})"
            echo "  MTTR: ${mttrMin} minutos"
            echo "  Nivel DevOps: ${nivel}"
            echo "========================================"

            currentBuild.description = "DORA: ${nivel} | Lead: ${leadTimeMin}min | Failure: ${failureRate}% | Deploys: ${deploysUltSemana}"
        }
    }
}
    }

    post {
        success {
            echo 'Pipeline completado - Smart-Liquor desplegado en http://57.156.66.168:8000'
        }
        failure {
            echo 'Pipeline fallo - revisar logs arriba'
        }
        always {
            echo 'Historial disponible en Jenkins para analisis DORA'
        }
    }
}
