
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
        
        for ep in endpoints:
            # Assumes ep.file_path is absolute or relative from root
            # We need checking relative path if possible, but assume absolute for now
            # Adjust based on project root? 
            # In main.py we scan absolute paths. 
            # Let's try to make them relative to common root.
            
            parts = ep.file_path.replace("\\", "/").split("/")
            # Naive heuristic: Group by parent directory of the file
            parent_dir = os.path.dirname(ep.file_path)
            dir_name = os.path.basename(parent_dir)
            
            # Simple clustering: Just one level up? Or full hierarchy?
            # Full hierarchy is better for Google-scale.
            # But let's start with "File Clustering" -> Group by Directory.
            
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
        
        final_nodes = list(root_clusters.values())
        
        # Performance: If we have too many clusters, we recursively cluster them?
        # For now, 1-level directory clustering is a huge win over 1000 flat files.
        
        return final_nodes
