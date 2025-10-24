pipeline {
    agent [label '']

    environment {
        APP_HOME = '/opt/plagiarism-app'
        PYTHON = '/lib/python3.6/'
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
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    deactivate
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