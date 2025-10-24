pipeline {
    agent [label '']
    stages {
        stage('Checkout') {
            steps {
                git url: 'https://github.com/your-repo/python-project.git', branch: 'main'
            }
        }
        stage('Build') {
            steps {
                sh '''
                python3 -m venv venv
                . venv/bin/activate
                pip install -r requirements.txt
                '''
            }
        }
        stage('Test') {  // 可选：运行测试
            steps {
                sh '''
                . venv/bin/activate
                pytest  # 假设有pytest测试
                '''
            }
        }
        stage('Deploy') {
            steps {
                sshPublisher(
                    publishers: [
                        sshPublisherDesc(
                            configName: 'Target-Server',  // 在系统配置中定义的SSH主机名
                            transfers: [
                                sshTransfer(
                                    sourceFiles: 'venv/',  // 传输虚拟环境或打包文件
                                    remoteDirectory: '/opt/myapp/',  // 目标机部署目录
                                    execCommand: '''
                                        cd /opt/myapp/
                                        deactivate || true  # 如果有旧环境
                                        rm -rf venv  # 清理旧环境
                                        # 解压或直接使用传输的文件
                                        source venv/bin/activate
                                        nohup python app.py > app.log 2>&1 &  # 后台运行
                                    '''
                                )
                            ]
                        )
                    ]
                )
            }
        }
    }
    post {
        always {
            emailext(  // 可选：邮件通知，需安装Email Extension插件
                subject: "Build ${currentBuild.currentResult}: ${env.JOB_NAME}",
                body: "Check console output at ${env.BUILD_URL} to view the results.",
                to: 'your-email@example.com'
            )
        }
    }
}