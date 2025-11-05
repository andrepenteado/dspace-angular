build:
	export NODE_OPTIONS="--max_old_space_size=4096"
	echo $(GITHUB_TOKEN) | docker login ghcr.io --username andrepenteado --password-stdin
	yarn run build:prod
	docker buildx build -f Dockerfile.dist -t ghcr.io/andrepenteado/dspace-angular/7_x-dist:1.0.0 --push .
