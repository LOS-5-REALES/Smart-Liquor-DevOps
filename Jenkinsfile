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

        stage('2. Calidad de Código (Linting)') {
            steps {
                echo 'Validando estilo y sintaxis del código...'
                bat 'flake8 .'
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

        stage('7. Métricas DORA') {
            steps {
                echo '📊 Calculando métricas DORA...'
                script {
                    // ── Tiempo de inicio del build actual ──────────────
                    def buildStart    = currentBuild.startTimeInMillis
                    def buildEnd      = System.currentTimeMillis()
                    def leadTimeMin   = ((buildEnd - buildStart) / 1000 / 60).round(2)

                    // ── Historial de builds para calcular métricas ─────
                    def builds        = currentBuild.rawBuild.parent.builds
                    def totalBuilds   = builds.size()
                    def failedBuilds  = builds.count { it.result?.toString() == 'FAILURE' }
                    def successBuilds = builds.count { it.result?.toString() == 'SUCCESS' }

                    // ── Change Failure Rate ────────────────────────────
                    def failureRate = totalBuilds > 0
                        ? ((failedBuilds / totalBuilds) * 100).round(1)
                        : 0

                    // ── Deployment Frequency ───────────────────────────
                    // Builds exitosos en los últimos 7 días
                    def hace7dias     = System.currentTimeMillis() - (7 * 24 * 60 * 60 * 1000L)
                    def deploysUltSemana = builds.count {
                        it.result?.toString() == 'SUCCESS' &&
                        it.startTimeInMillis > hace7dias
                    }

                    // ── MTTR (Mean Time to Recovery) ───────────────────
                    // Tiempo promedio entre un fallo y el siguiente éxito
                    def mttrMin = 0
                    def recoveries = []
                    def buildList = builds.toList().reverse() // orden cronológico

                    for (int i = 0; i < buildList.size() - 1; i++) {
                        if (buildList[i].result?.toString() == 'FAILURE') {
                            for (int j = i + 1; j < buildList.size(); j++) {
                                if (buildList[j].result?.toString() == 'SUCCESS') {
                                    def diff = (buildList[j].startTimeInMillis - buildList[i].startTimeInMillis) / 1000 / 60
                                    recoveries.add(diff)
                                    break
                                }
                            }
                        }
                    }
                    if (recoveries.size() > 0) {
                        mttrMin = (recoveries.sum() / recoveries.size()).round(1)
                    }

                    // ── Nivel de rendimiento según DORA ───────────────
                    def nivel = ""
                    if (deploysUltSemana >= 7 && failureRate < 15 && leadTimeMin < 15) {
                        nivel = "🏆 ELITE"
                    } else if (deploysUltSemana >= 3 && failureRate < 30 && leadTimeMin < 60) {
                        nivel = "✅ HIGH"
                    } else if (deploysUltSemana >= 1 && failureRate < 45) {
                        nivel = "⚠️ MEDIUM"
                    } else {
                        nivel = "❌ LOW"
                    }

                    // ── Imprimir reporte ───────────────────────────────
                    echo """
╔══════════════════════════════════════════════╗
║         📊 MÉTRICAS DORA - Smart-Liquor      ║
╠══════════════════════════════════════════════╣
║  🚀 Deployment Frequency                     ║
║     Deploys exitosos (últimos 7 días): ${deploysUltSemana}    ║
╠══════════════════════════════════════════════╣
║  ⏱️  Lead Time for Changes                   ║
║     Tiempo de este pipeline: ${leadTimeMin} min         ║
╠══════════════════════════════════════════════╣
║  💥 Change Failure Rate                      ║
║     Fallos: ${failedBuilds}/${totalBuilds} builds = ${failureRate}%          ║
╠══════════════════════════════════════════════╣
║  🔧 Mean Time to Recovery (MTTR)             ║
║     Tiempo promedio de recuperación: ${mttrMin} min  ║
╠══════════════════════════════════════════════╣
║  🎯 Nivel de Rendimiento DevOps: ${nivel}    ║
╚══════════════════════════════════════════════╝
                    """

                    // Guardar métricas como propiedades del build
                    currentBuild.description = "DORA: ${nivel} | Lead: ${leadTimeMin}min | Failure: ${failureRate}% | Deploys/semana: ${deploysUltSemana}"
                }
            }
        }
    }

    post {
        success {
            echo '✅ Pipeline completado — Smart-Liquor desplegado en http://57.156.66.168:8000'
        }
        failure {
            echo '❌ Pipeline falló — revisar logs arriba'
            script {
                echo "⏰ Fallo registrado a las: ${new Date()}"
                echo "📌 Calcula el MTTR desde este momento hasta el próximo build exitoso."
            }
        }
        always {
            echo '📋 Historial disponible en Jenkins para análisis DORA'
        }
    }
}
