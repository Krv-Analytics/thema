"Select models for analysis from structural equivalency classes of Graph Models based on best coverage."


import argparse
import sys
import os
import pickle
from dotenv import load_dotenv
import json

from model_selector_helper import (
    read_graph_clustering,
    select_models,
    plot_mapper_histogram,
)

load_dotenv()
src = os.getenv("src")
sys.path.append(src)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    root = os.getenv("root")
    JSON_PATH = os.getenv("params")
    if os.path.isfile(JSON_PATH):
        with open(JSON_PATH, "r") as f:
            params_json = json.load(f)
    else:
        print("params.json file note found!")

    parser.add_argument(
        "-m",
        "--metric",
        type=str,
        default=params_json["dendrogram_metric"],
        help="Select metric that defines the precomputed agglomerative clustering model.",
    )

    parser.add_argument(
        "-n",
        "--num_groups",
        type=int,
        default=2,
        help="Select folder of mapper objects to compare,identified by the number of policy groups.",
    )

    parser.add_argument(
        "-H",
        "--histogram",
        default=False,
        action="store_true",
        help="Select folder of mapper objects to compare,identified by the number of policy groups.",
    )

    parser.add_argument(
        "--coverage_filter",
        type=float,
        default=params_json["histogram_coverage"],
        help="A minimum model coverage for visualizing a histogram. Only set when using '-H' tag as well.",
    )

    parser.add_argument(
        "-v",
        "--Verbose",
        default=False,
        action="store_true",
        help="If set, will print messages detailing computation and output.",
    )

    args = parser.parse_args()
    this = sys.modules[__name__]

    # Read in Keys and distances from pickle file
    n = args.num_groups
    models_dir = "data/"+params_json["Run_Name"] + f"/models/"
    # Visualize Model Distribution
    if args.histogram:
        plot_mapper_histogram(models_dir, args.coverage_filter)

    # Choose ~best~ models from curvature equivalency classes.
    # Current implementation chooses Model with the best coverage.
    else:

        rel_cluster_dir = "data/" + params_json["Run_Name"] + f"/model_analysis/graph_clustering/{n}_policy_groups/"
        cluster_dir = os.path.join(
            root, rel_cluster_dir)

        keys, clustering, distance_threshold = read_graph_clustering(cluster_dir,
            metric=args.metric, n=n
        )

        rel_model_dir = "data/" + params_json["Run_Name"] + f"/models/{n}_policy_groups/" 
        model_dir = os.path.join(
            root, rel_model_dir
        )
        models = select_models(model_dir, keys, clustering, n)

        model_file = (
            f"equivalence_class_candidates_{args.metric}_{distance_threshold}DT.pkl"
        )

        out_dir_message = f"{model_file} successfully written."

        rel_outdir = "data/" + params_json["Run_Name"] + f"/model_analysis/token_models/"
        output_dir = os.path.join(root, rel_outdir)
        # Check if output directory already exists
        if os.path.isdir(output_dir):
            model_file = os.path.join(output_dir, model_file)

        else:
            os.makedirs(output_dir, exist_ok=True)
            model_file = os.path.join(output_dir, model_file)
        with open(model_file, "wb") as handle:
            pickle.dump(models, handle, protocol=pickle.HIGHEST_PROTOCOL)

        if args.Verbose:
            print("\n")
            print(
                "-------------------------------------------------------------------------------- \n\n"
            )
            print(f"{out_dir_message}")

            print(
                "\n\n -------------------------------------------------------------------------------- "
            )
