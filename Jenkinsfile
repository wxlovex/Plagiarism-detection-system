// pipeline {
//     agent any
//
//     environment {
//         APP_HOME = '/opt/plagiarism-app'
//         PYTHON = '/usr/bin/Python-3.12.12/python'
//         VENV = "${APP_HOME}/venv"
//         TARGET_HOST = 'hadoop103'
//         TARGET_USER = 'user2201'
//         REDIS_HOST = '192.168.119.102'  // 容器内链接
//         REDIS_PORT = '6379'
//         USE_REDIS = '0'
//     }
//
//     stages {
//         stage('Checkout') {
//             steps {
//                 echo 'Pulling code from Git...'
//                 checkout scm
//             }
//         }
//
//         stage('Build') {
//             steps {
//                 echo 'Installing dependencies...'
//                 sh """
//                     rm -rf ${APP_HOME}
//                     mkdir -p ${APP_HOME}
//                     cp -r * ${APP_HOME}/
//                     cd ${APP_HOME}
//                     ${PYTHON} -m venv ${VENV}
//                     source ${VENV}/bin/activate
//                     ${VENV}/bin/pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 --retries 3
//                     ${VENV}/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 --retries 3
//                     deactivate
//                     sudo mkdir -p ${APP_HOME}/uploads
//                     sudo chown -R root:root ${APP_HOME}/uploads  # root可写（systemd用root）
//                     sudo chmod 755 ${APP_HOME}/uploads
//                 """
//             }
//         }
//
//         stage('Deploy') {
//             steps {
//                 echo 'Deploying service...'
//                 sh """
//                     cd ${APP_HOME}
//                     source ${VENV}/bin/activate
//                     nohup gunicorn --bind 0.0.0.0:5000 app:app > gunicorn.log 2>&1 &
//                     deactivate
//                 """
//                 sleep 5
//             }
//         }
//
//         stage('Test') {
//             steps {
//                 echo 'Running simple test...'
//                 sh """
//                     curl -f http://localhost:5000 || echo 'Test failed'
//                 """
//             }
//         }
//
//         stage('Image') {
//             steps {
//                 echo '构建镜像并传输到目标机运行'
//                 sh '''
//                     # 建Docker镜像（在当前机）
//                     cd ${APP_HOME}
//                     docker build -t plagiarism-detection:latest .
//
//                     # 导出tar
//                     docker save -o app.tar plagiarism-detection:latest
//
//                     # Fix权限
//                     sudo chown ${USER}:${USER} app.tar  # Jenkins workspace用户
//                     chmod 644 app.tar
//
//                     # SCP tar到目标机
//                     sudo -u user2201 scp -o StrictHostKeyChecking=no app.tar ${TARGET_USER}@${TARGET_HOST}:/tmp/
//
//                     # SSH到目标机导入+运行（清理旧容器）
//                     sudo -u user2201 ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_HOST} "
//                         docker load -i /tmp/app.tar
//                         docker rm -f plagiarism-app || true
//                         docker run -d -p 5000:5000 --restart=always --name plagiarism-app plagiarism-detection:latest
//                         rm /tmp/app.tar
//                         echo '目标机Docker运行成功'
//                     "
//
//                     # 清理当前机tar
//                     rm app.tar
//                 '''
//             }
//         }
//
//     }
//
//     post {
//         always {
//             echo 'Cleanup...'
//         }
//         success {
//             echo 'Deployment successful! Access http://your-server-ip:5000'
//         }
//         failure {
//             echo 'Deployment failed!'
//         }
//     }
// }

pipeline {
    agent any

    environment {
        TARGET_HOST = 'hadoop103'
        TARGET_USER = 'user2201'
        REDIS_HOST  = '192.168.119.102'
        REDIS_PORT  = '6379'
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Pulling code from Git...'
                checkout scm
            }
        }

        stage('Docker Build') {
            steps {
                echo 'Building Docker image with Python 3.12...'
                sh 'docker build -t plagiarism-detection:latest .'
            }
        }

        stage('Test Image') {
            steps {
                echo 'Testing Docker image locally...'
                sh '''
                    docker run --rm -d -p 5001:5000 --name test-plagiarism plagiarism-detection:latest
                    sleep 5
                    curl -f http://localhost:5001 || echo 'Test failed'
                    docker stop test-plagiarism || true
                '''
            }
        }

        stage('Deploy to Target') {
            steps {
                echo 'Deploying to hadoop103...'
                sh '''
                    docker save -o app.tar plagiarism-detection:latest

                    sudo chown ${USER}:${USER} app.tar
                    chmod 644 app.tar

                    sudo -u ${TARGET_USER} scp -o StrictHostKeyChecking=no app.tar ${TARGET_USER}@${TARGET_HOST}:/tmp/

                    sudo -u ${TARGET_USER} ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_HOST} "
                        docker load -i /tmp/app.tar
                        docker rm -f plagiarism-app || true
                        docker rm -f $(docker ps -aq) 2>/dev/null || true
                        docker run -d \
                            -p 5000:5000 \
                            --restart=always \
                            --name plagiarism-app \
                            -e REDIS_HOST=${REDIS_HOST} \
                            -e REDIS_PORT=${REDIS_PORT} \
                            -e MYSQL_HOST=192.168.119.102 \
                            -e MYSQL_PORT=3306 \
                            -e MYSQL_USER=root \
                            -e MYSQL_PASSWORD=123456 \
                            -e MYSQL_DATABASE=plagiarism_db \
                            plagiarism-detection:latest
                        rm /tmp/app.tar
                        echo '✅ 部署成功！访问 http://${TARGET_HOST}:5000'
                    "
                    rm -f app.tar
                '''
            }
        }
    }

    post {
        success { echo '🎉 全部成功！Cpolar 公网地址可直接访问' }
        failure { echo '❌ 失败，请看上面日志' }
    }
}