
from typing import List, Dict, Any
from models import EndpointNodes
import os

class ClusterManager:
    def cluster_endpoints(self, endpoints: List[EndpointNodes]) -> List[EndpointNodes]:
        """
        Group endpoints by directory structure.
        """
        root_clusters: Dict[str, EndpointNodes] = {}
        processed_endpoints = []
        
        # 1. Identify common directories
        # Create a tree structure
        tree = {}
        
        unclustered_nodes = []
        
        for ep in endpoints:
            # 1. Hoist Routes (type='root') to Top Level
            # The User wants "Web Service Structure", so Routes should be visible immediately, not hidden in folders.
            if ep.type == 'root':
                unclustered_nodes.append(ep)
                continue

            # 2. Cluster others (Helpers, Files without routes, etc.)
            parts = ep.file_path.replace("\\", "/").split("/")
            parent_dir = os.path.dirname(ep.file_path)
            dir_name = os.path.basename(parent_dir)
            
            if parent_dir not in root_clusters:
                root_clusters[parent_dir] = EndpointNodes(
                    id=f"cluster-{parent_dir}",
                    path=dir_name if dir_name else "Root",
                    method="CLUSTER",
                    language="folder",
                    file_path=parent_dir,
                    line_number=0,
                    type="cluster",
                    children=[]
                )
            
            root_clusters[parent_dir].children.append(ep)
            
        # 2. Convert to list
        # If we just return the clusters, we lose the direct file access at top level
        # But that's the point of clustering.
        
        # If a directory has only 1 file, maybe don't cluster?
        # For consistency, usually better to cluster all or nothing.
        
        final_nodes = unclustered_nodes + list(root_clusters.values())
        
        return final_nodes
