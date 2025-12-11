build:
	echo $(GITHUB_TOKEN) | docker login ghcr.io --username andrepenteado --password-stdin
	NODE_OPTIONS="--max_old_space_size=4096" yarn build
	docker buildx build -f Dockerfile -t ghcr.io/andrepenteado/dspace-angular/7_x:1.0.0 --push .
