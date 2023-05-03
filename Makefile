# Makefile 

all: fetch-coal-data coal-data-cleaner 

install: check-poetry 
	@echo " Generating and populating .env file..."
	python scripts/setup.py
	@echo "Installing necessary dependencies..." 
	poetry run pip install python-dotenv pandas pymongo scikit-learn umap-learn hdbscan kmapper networkx matplotlib seaborn giotto-tda


uninstall: clean
	@echo "Removing Dependencies from Poetry environment..."
	poetry run pip uninstall python-dotenv pandas pymongo scikit-learn umap-learn hdbscan kmapper networkx matplotlib seaborn giotto-tda
	@echo "Removing Poetry"
	sudo pip uninstall poetry 
	rm -f .env 

check-poetry:
	@which poetry || (echo "Poetry is not installed. Installing..."; sudo pip install poetry; poetry install;)

fetch-coal-data:
	python src/processing/pulling/data_generator.py -v

coal-data-cleaner:
	python src/processing/cleaning/cleaner.py -v

clean-raw: 
	rm -f data/raw/* 

clean-cleaned: 
	rm -f data/clean/*

clean-projections:
	rm -f -r data/projections/*

clean: clean-raw clean-cleaned clean-projections 
	rm -f -r data/


