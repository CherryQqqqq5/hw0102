set -eu

mkdir -p /opt/benchmark-python /opt/benchmark-packages /opt/benchmark-tmp
export TMPDIR=/opt/benchmark-tmp
tar -xzf /benchmark-setup/python-3.12.13-linux-x86_64.tar.gz \
    -C /opt/benchmark-python --strip-components=1
/opt/benchmark-python/bin/python3.12 -m pip install --no-cache-dir --target /opt/benchmark-packages \
    --timeout 30 --retries 1 --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
    'mailman==3.3.8' 'pytest-json-ctrf==0.3.5' 'pytest==8.4.1'
tar -czf /benchmark-setup/mailman-deps.tar.gz -C /opt/benchmark-packages .
