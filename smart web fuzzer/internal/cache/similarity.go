// Package cache provides similarity hashing for deduplication.
package cache

import (
	"crypto/md5"
	"encoding/binary"
	"hash/fnv"
	"math"
	"sort"
	"sync"
)

// SimHash implements locality-sensitive hashing for similarity detection
type SimHash struct {
	bits int
}

// NewSimHash creates a new SimHash instance
func NewSimHash(bits int) *SimHash {
	if bits <= 0 {
		bits = 64
	}
	return &SimHash{bits: bits}
}

// Hash computes a similarity hash for the data
func (sh *SimHash) Hash(data []byte) uint64 {
	// Convert data to features (shingles)
	features := sh.shingle(data, 4)

	// Compute weighted bit vectors
	v := make([]int, sh.bits)

	for _, feature := range features {
		h := fnv.New64a()
		h.Write([]byte(feature))
		hash := h.Sum64()

		for i := 0; i < sh.bits; i++ {
			bit := (hash >> uint(i)) & 1
			if bit == 1 {
				v[i]++
			} else {
				v[i]--
			}
		}
	}

	// Convert to fingerprint
	var fingerprint uint64
	for i := 0; i < sh.bits; i++ {
		if v[i] >= 0 {
			fingerprint |= 1 << uint(i)
		}
	}

	return fingerprint
}

// shingle creates n-grams from data
func (sh *SimHash) shingle(data []byte, n int) []string {
	if len(data) < n {
		return []string{string(data)}
	}

	shingles := make([]string, 0, len(data)-n+1)
	for i := 0; i <= len(data)-n; i++ {
		shingles = append(shingles, string(data[i:i+n]))
	}

	return shingles
}

// Similarity computes Hamming distance similarity between two hashes
func (sh *SimHash) Similarity(h1, h2 uint64) float64 {
	distance := hammingDistance(h1, h2)
	return 1.0 - float64(distance)/float64(sh.bits)
}

// hammingDistance counts differing bits
func hammingDistance(a, b uint64) int {
	xor := a ^ b
	count := 0
	for xor != 0 {
		count++
		xor &= xor - 1
	}
	return count
}

// MinHash implements MinHash for Jaccard similarity estimation
type MinHash struct {
	numHashes int
	hashFuncs []func([]byte) uint64
}

// NewMinHash creates a new MinHash instance
func NewMinHash(numHashes int) *MinHash {
	if numHashes <= 0 {
		numHashes = 128
	}

	mh := &MinHash{
		numHashes: numHashes,
		hashFuncs: make([]func([]byte) uint64, numHashes),
	}

	// Generate hash functions using different seeds
	for i := 0; i < numHashes; i++ {
		seed := uint64(i)
		mh.hashFuncs[i] = func(data []byte) uint64 {
			h := fnv.New64a()
			seedBytes := make([]byte, 8)
			binary.LittleEndian.PutUint64(seedBytes, seed)
			h.Write(seedBytes)
			h.Write(data)
			return h.Sum64()
		}
	}

	return mh
}

// Signature computes the MinHash signature
func (mh *MinHash) Signature(data []byte) []uint64 {
	shingles := shingle(data, 4)

	signature := make([]uint64, mh.numHashes)
	for i := range signature {
		signature[i] = math.MaxUint64
	}

	for _, s := range shingles {
		for i, hashFunc := range mh.hashFuncs {
			h := hashFunc([]byte(s))
			if h < signature[i] {
				signature[i] = h
			}
		}
	}

	return signature
}

// EstimateSimilarity estimates Jaccard similarity from signatures
func (mh *MinHash) EstimateSimilarity(sig1, sig2 []uint64) float64 {
	if len(sig1) != len(sig2) {
		return 0
	}

	matches := 0
	for i := range sig1 {
		if sig1[i] == sig2[i] {
			matches++
		}
	}

	return float64(matches) / float64(len(sig1))
}

// shingle helper function
func shingle(data []byte, n int) []string {
	if len(data) < n {
		return []string{string(data)}
	}

	shingles := make([]string, 0, len(data)-n+1)
	for i := 0; i <= len(data)-n; i++ {
		shingles = append(shingles, string(data[i:i+n]))
	}

	return shingles
}

// SimilarityCache stores and queries similar items
type SimilarityCache struct {
	simHash   *SimHash
	items     map[uint64][]CachedItem
	threshold float64
	mu        sync.RWMutex
}

// CachedItem represents an item in the similarity cache
type CachedItem struct {
	Key      string
	Hash     uint64
	Data     []byte
	Metadata interface{}
}

// NewSimilarityCache creates a new similarity cache
func NewSimilarityCache(threshold float64) *SimilarityCache {
	if threshold <= 0 {
		threshold = 0.9 // 90% similarity threshold
	}
	return &SimilarityCache{
		simHash:   NewSimHash(64),
		items:     make(map[uint64][]CachedItem),
		threshold: threshold,
	}
}

// Add adds an item to the cache
func (sc *SimilarityCache) Add(key string, data []byte, metadata interface{}) uint64 {
	hash := sc.simHash.Hash(data)

	sc.mu.Lock()
	defer sc.mu.Unlock()

	// Use bucket-based storage for O(1) similar lookups
	bucket := hash >> 4 // Use top bits as bucket key

	item := CachedItem{
		Key:      key,
		Hash:     hash,
		Data:     data,
		Metadata: metadata,
	}

	sc.items[bucket] = append(sc.items[bucket], item)

	return hash
}

// FindSimilar finds items similar to the given data
func (sc *SimilarityCache) FindSimilar(data []byte) []CachedItem {
	hash := sc.simHash.Hash(data)

	sc.mu.RLock()
	defer sc.mu.RUnlock()

	var similar []CachedItem
	bucket := hash >> 4

	// Check items in the same bucket
	for _, item := range sc.items[bucket] {
		similarity := sc.simHash.Similarity(hash, item.Hash)
		if similarity >= sc.threshold {
			similar = append(similar, item)
		}
	}

	return similar
}

// IsDuplicate checks if similar content already exists
func (sc *SimilarityCache) IsDuplicate(data []byte) bool {
	similar := sc.FindSimilar(data)
	return len(similar) > 0
}

// GetStats returns cache statistics
func (sc *SimilarityCache) GetStats() map[string]interface{} {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	totalItems := 0
	for _, items := range sc.items {
		totalItems += len(items)
	}

	return map[string]interface{}{
		"buckets":   len(sc.items),
		"items":     totalItems,
		"threshold": sc.threshold,
	}
}

// ContentFingerprint generates a content fingerprint for deduplication
type ContentFingerprint struct {
	Hash     string
	Size     int
	Checksum uint32
}

// GenerateFingerprint generates a fingerprint for content
func GenerateFingerprint(data []byte) ContentFingerprint {
	// MD5 for quick content hash
	sum := md5.Sum(data)

	// FNV for checksum
	h := fnv.New32a()
	h.Write(data)

	return ContentFingerprint{
		Hash:     string(sum[:]),
		Size:     len(data),
		Checksum: h.Sum32(),
	}
}

// Equals checks if two fingerprints match
func (fp ContentFingerprint) Equals(other ContentFingerprint) bool {
	return fp.Hash == other.Hash && fp.Size == other.Size && fp.Checksum == other.Checksum
}

// DeduplicationCache provides content deduplication
type DeduplicationCache struct {
	fingerprints map[string]ContentFingerprint
	mu           sync.RWMutex
}

// NewDeduplicationCache creates a new deduplication cache
func NewDeduplicationCache() *DeduplicationCache {
	return &DeduplicationCache{
		fingerprints: make(map[string]ContentFingerprint),
	}
}

// Add adds content and returns true if it's new (not a duplicate)
func (dc *DeduplicationCache) Add(key string, data []byte) bool {
	fp := GenerateFingerprint(data)

	dc.mu.Lock()
	defer dc.mu.Unlock()

	// Check if fingerprint already exists
	for _, existing := range dc.fingerprints {
		if fp.Equals(existing) {
			return false // Duplicate
		}
	}

	dc.fingerprints[key] = fp
	return true
}

// IsDuplicate checks if content is a duplicate
func (dc *DeduplicationCache) IsDuplicate(data []byte) bool {
	fp := GenerateFingerprint(data)

	dc.mu.RLock()
	defer dc.mu.RUnlock()

	for _, existing := range dc.fingerprints {
		if fp.Equals(existing) {
			return true
		}
	}

	return false
}

// LSHIndex implements Locality-Sensitive Hashing index
type LSHIndex struct {
	bands      int
	rows       int
	buckets    []map[string][]string // band -> hash -> keys
	signatures map[string][]uint64   // key -> signature
	minHash    *MinHash
	mu         sync.RWMutex
}

// NewLSHIndex creates a new LSH index
func NewLSHIndex(bands, rows int) *LSHIndex {
	if bands <= 0 {
		bands = 20
	}
	if rows <= 0 {
		rows = 5
	}

	buckets := make([]map[string][]string, bands)
	for i := range buckets {
		buckets[i] = make(map[string][]string)
	}

	return &LSHIndex{
		bands:      bands,
		rows:       rows,
		buckets:    buckets,
		signatures: make(map[string][]uint64),
		minHash:    NewMinHash(bands * rows),
	}
}

// Insert inserts data into the index
func (idx *LSHIndex) Insert(key string, data []byte) {
	sig := idx.minHash.Signature(data)

	idx.mu.Lock()
	defer idx.mu.Unlock()

	idx.signatures[key] = sig

	// Hash into bands
	for b := 0; b < idx.bands; b++ {
		start := b * idx.rows
		end := start + idx.rows
		bandSig := sig[start:end]

		// Create band hash
		h := fnv.New64a()
		for _, v := range bandSig {
			binary.Write(h, binary.LittleEndian, v)
		}
		bandHash := string(h.Sum(nil))

		idx.buckets[b][bandHash] = append(idx.buckets[b][bandHash], key)
	}
}

// Query finds similar items
func (idx *LSHIndex) Query(data []byte) []string {
	sig := idx.minHash.Signature(data)

	idx.mu.RLock()
	defer idx.mu.RUnlock()

	candidates := make(map[string]bool)

	// Find candidates from each band
	for b := 0; b < idx.bands; b++ {
		start := b * idx.rows
		end := start + idx.rows
		bandSig := sig[start:end]

		h := fnv.New64a()
		for _, v := range bandSig {
			binary.Write(h, binary.LittleEndian, v)
		}
		bandHash := string(h.Sum(nil))

		for _, key := range idx.buckets[b][bandHash] {
			candidates[key] = true
		}
	}

	// Convert to slice
	result := make([]string, 0, len(candidates))
	for key := range candidates {
		result = append(result, key)
	}

	sort.Strings(result)
	return result
}
