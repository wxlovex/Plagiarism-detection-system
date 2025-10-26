pipeline {
    agent any

    environment {
        APP_HOME = '/opt/plagiarism-app'
        PYTHON = '/usr/bin/python3.6'
        VENV = "${APP_HOME}/venv"
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Pulling code from Git...'
                checkout scm
            }
        }

        stage('Build') {
            steps {
                echo 'Installing dependencies...'
                sh """
                    rm -rf ${APP_HOME}
                    mkdir -p ${APP_HOME}
                    cp -r * ${APP_HOME}/
                    cd ${APP_HOME}
                    ${PYTHON} -m venv ${VENV}
                    source ${VENV}/bin/activate
                    ${VENV}/bin/pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 --retries 3
                    ${VENV}/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 --retries 3
                    deactivate
                    sudo mkdir -p ${APP_HOME}/uploads
                    sudo chown -R root:root ${APP_HOME}/uploads  # root可写（systemd用root）
                    sudo chmod 755 ${APP_HOME}/uploads
                """
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deploying service...'
                sh """
                    cd ${APP_HOME}
                    source ${VENV}/bin/activate
                    nohup gunicorn --bind 0.0.0.0:5000 app:app > gunicorn.log 2>&1 &
                    deactivate
                """
                sleep 5
            }
        }

        stage('Test') {
            steps {
                echo 'Running simple test...'
                sh """
                    curl -f http://localhost:5000 || echo 'Test failed'
                """
            }
        }

        stage('Image') {
            steps {
                echo '构建镜像传输到目标机并运行'
                sh """
                    su user2201
                    ssh user2201@192.168.119.103 -o StrictHostKeyChecking=no 'bash -s' < /home/user2201/pla.sh
                """
            }
        }

    }

    post {
        always {
            echo 'Cleanup...'
        }
        success {
            echo 'Deployment successful! Access http://your-server-ip:5000'
        }
        failure {
            echo 'Deployment failed!'
        }
    }
}