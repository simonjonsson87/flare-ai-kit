# Docker commands

Build the example. Note MUST BE EXECUTED FROM flare-ai-kit ROOT
```docker build --no-cache --progress=plain -t flare-ai-kit-web-chatbot -f examples/web-chatbot/Dockerfile .```

Run the container and start the servers
```docker run --rm -p 80:80 -it --env-file .env flare-ai-kit-web-chatbot```

Clear containers and images
```docker builder prune --all```

List containers
```docker ps ```

Copy self-signed certificate from the docker container
```docker cp <CONTAINER ID>:/app/certs/server_cert.pem ./server_cert.pem```


## Clear all docker images, build, and then run the container
```zsh
docker builder prune --all &&
docker build --no-cache --progress=plain -t flare-ai-kit-web-chatbot -f examples/web-chatbot/Dockerfile . > build.log 2>&1 &&
docker run --rm -p 80:80 -it --env-file .env flare-ai-kit-web-chatbot
```

# Debug

Check if the port is exposed 
```netstat -a -n | grep 8080```

Connect with curl using self-signed certificate
```curl -v --cacert server_cert.pem https://localhost:8080/api/routes/chat```

# Use self-signed certificate

List docker containers to get the CONTAINER ID and then copy the certificate out from from the container
```
docker ps
docker cp <CONTAINER ID>:/app/certs/server_cert.pem ./server_cert.pem
```

Add the certificate to your browser
