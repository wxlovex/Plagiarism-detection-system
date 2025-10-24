pipeline {
    agent [label '']  // 任何节点跑（默认master）

    environment {
        APP_HOME = '/opt/plagiarism-app'  // 部署目录
        PYTHON = '/lib/python3.6/'  // Python
        VENV = "${APP_HOME}/venv"
    }

    stages {
        stage('Checkout') {
            steps {
                echo '拉取代码...'
                checkout scm  // 从Git拉（项目配置的repo）
            }
        }

        stage('Build') {
            steps {
                echo '安装依赖...'
                sh """
                    rm -rf ${APP_HOME}  // 清旧部署
                    mkdir -p ${APP_HOME}
                    cp -r * ${APP_HOME}/  // 复制项目文件
                    cd ${APP_HOME}
                    ${PYTHON} -m venv ${VENV}
                    source ${VENV}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt  // 需加requirements.txt
                    deactivate
                """
            }
        }

        stage('Deploy') {
            steps {
                echo '部署服务...'
                sh """
                    cd ${APP_HOME}
                    source ${VENV}/bin/activate
                    nohup gunicorn --bind 0.0.0.0:5000 app:app > gunicorn.log 2>&1 &  // 后台跑
                    deactivate
                """
                sleep 5  // 等启动
            }
        }

        stage('Test') {
            steps {
                echo '简单测试...'
                sh """
                    curl -f http://localhost:5000 || echo '测试失败'
                """
            }
        }
    }

    post {
        always {
            echo '清理...'
            // 可加邮件通知：mail to: 'your@email.com' ...
        }
        success {
            echo '部署成功！访问 http://your-ip:5000'
        }
        failure {
            echo '部署失败！'
        }
    }
}