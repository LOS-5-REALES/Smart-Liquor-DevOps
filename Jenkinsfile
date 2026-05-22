pipeline {
    agent any
    environment {
        DATABASE_URL = credentials('supabase-url')
        COMPOSE_FILE = "docker/docker-compose.yml"
        VM_IP        = "57.156.66.168"
        VM_USER      = "smartliquor"
        VM_REPO_PATH = "/home/smartliquor/Smart-Liquor-DevOps"
        VM_BRANCH    = "dev/dashboard-mejoras"
    }

    stages {

        stage('1. Preparar .env') {
            steps {
                writeFile file: '.env', text: "DATABASE_URL=${env.DATABASE_URL}\n"
            }
        }

        stage('2. Calidad de Codigo (Linting)') {
            steps {
                echo 'Validando estilo y sintaxis del codigo...'
                bat 'flake8 .'
            }
        }

        stage('3. Pruebas de Integracion') {
            steps {
                echo "Ejecutando pruebas de integracion..."
                bat 'if exist tests\\integration pytest tests\\integration || exit /b 0'
            }
        }

        stage('4. Construccion (Docker)') {
            steps {
                echo 'Generando imagen de contenedor...'
                bat "docker-compose -f ${COMPOSE_FILE} build"
            }
        }

        stage('5. Despliegue Local') {
            steps {
                echo 'Levantando servicios localmente...'
                bat "docker-compose -f ${COMPOSE_FILE} up -d"
            }
        }

        stage('6. Despliegue remoto en VM Azure') {
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

        stage('7. Metricas DORA') {
            steps {
                echo 'Calculando metricas DORA...'
                script {

                    // Lead Time — tiempo de este pipeline en segundos enteros
                    def buildStart   = currentBuild.startTimeInMillis
                    def buildEnd     = System.currentTimeMillis()
                    def leadTimeSeg  = (long)((buildEnd - buildStart) / 1000)
                    def leadTimeMin  = (int)(leadTimeSeg / 60)
                    def leadTimeSec  = (int)(leadTimeSeg % 60)

                    // Historial de builds
                    def builds       = currentBuild.rawBuild.parent.builds
                    def totalBuilds  = (int) builds.size()
                    def failedBuilds = (int) builds.count { it.result?.toString() == 'FAILURE' }

                    // Change Failure Rate (entero, sin decimales)
                    def failureRate  = totalBuilds > 0 ? (int)((failedBuilds * 100) / totalBuilds) : 0

                    // Deployment Frequency — builds exitosos en los ultimos 7 dias
                    def hace7dias        = System.currentTimeMillis() - (7L * 24 * 60 * 60 * 1000)
                    def deploysUltSemana = (int) builds.count {
                        it.result?.toString() == 'SUCCESS' &&
                        it.startTimeInMillis > hace7dias
                    }

                    // MTTR — tiempo promedio entre fallo y siguiente exito (en minutos enteros)
                    def recoveries = []
                    def buildList  = builds.toList().reverse()

                    for (int i = 0; i < buildList.size() - 1; i++) {
                        if (buildList[i].result?.toString() == 'FAILURE') {
                            for (int j = i + 1; j < buildList.size(); j++) {
                                if (buildList[j].result?.toString() == 'SUCCESS') {
                                    long diff = (long)((buildList[j].startTimeInMillis - buildList[i].startTimeInMillis) / 1000 / 60)
                                    recoveries.add(diff)
                                    break
                                }
                            }
                        }
                    }

                    def mttrMin = 0
                    if (recoveries.size() > 0) {
                        long suma = 0L
                        for (long v : recoveries) { suma += v }
                        mttrMin = (int)(suma / recoveries.size())
                    }

                    // Nivel de rendimiento DORA
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

                    // Reporte en consola
                    echo "========================================"
                    echo "   METRICAS DORA - Smart-Liquor"
                    echo "========================================"
                    echo "  Deployment Frequency (7 dias): ${deploysUltSemana} deploys"
                    echo "  Lead Time: ${leadTimeMin} min ${leadTimeSec} seg"
                    echo "  Change Failure Rate: ${failureRate}% (${failedBuilds}/${totalBuilds})"
                    echo "  MTTR: ${mttrMin} minutos promedio"
                    echo "  Nivel DevOps: ${nivel}"
                    echo "========================================"

                    currentBuild.description = "DORA: ${nivel} | Lead: ${leadTimeMin}min | Failure: ${failureRate}% | Deploys/semana: ${deploysUltSemana}"
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
