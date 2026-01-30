// Package memory provides streaming utilities for large responses.
package memory

import (
	"io"
	"sync"
)

// StreamConfig holds streaming configuration
type StreamConfig struct {
	ChunkSize     int   // Size of each chunk
	MaxBuffered   int   // Maximum buffered chunks
	MaxTotalBytes int64 // Maximum total bytes to read
}

// DefaultStreamConfig returns default streaming configuration
func DefaultStreamConfig() *StreamConfig {
	return &StreamConfig{
		ChunkSize:     32 * 1024,         // 32KB chunks
		MaxBuffered:   4,                 // 4 buffered chunks
		MaxTotalBytes: 100 * 1024 * 1024, // 100MB max
	}
}

// ChunkedReader reads data in chunks to reduce memory pressure
type ChunkedReader struct {
	reader    io.Reader
	config    *StreamConfig
	bytesRead int64
	closed    bool
	mu        sync.Mutex
}

// NewChunkedReader creates a new chunked reader
func NewChunkedReader(reader io.Reader, config *StreamConfig) *ChunkedReader {
	if config == nil {
		config = DefaultStreamConfig()
	}
	return &ChunkedReader{
		reader: reader,
		config: config,
	}
}

// ReadChunk reads a single chunk
func (cr *ChunkedReader) ReadChunk() ([]byte, error) {
	cr.mu.Lock()
	defer cr.mu.Unlock()

	if cr.closed {
		return nil, io.EOF
	}

	// Check if we've reached the limit
	if cr.bytesRead >= cr.config.MaxTotalBytes {
		return nil, io.EOF
	}

	chunk := GetBytes(cr.config.ChunkSize)
	n, err := cr.reader.Read(chunk)

	if n > 0 {
		cr.bytesRead += int64(n)
		return chunk[:n], err
	}

	PutBytes(chunk)
	return nil, err
}

// BytesRead returns total bytes read
func (cr *ChunkedReader) BytesRead() int64 {
	cr.mu.Lock()
	defer cr.mu.Unlock()
	return cr.bytesRead
}

// Close marks the reader as closed
func (cr *ChunkedReader) Close() error {
	cr.mu.Lock()
	defer cr.mu.Unlock()
	cr.closed = true
	return nil
}

// StreamWriter writes data in chunks
type StreamWriter struct {
	writer       io.Writer
	config       *StreamConfig
	bytesWritten int64
	mu           sync.Mutex
}

// NewStreamWriter creates a new stream writer
func NewStreamWriter(writer io.Writer, config *StreamConfig) *StreamWriter {
	if config == nil {
		config = DefaultStreamConfig()
	}
	return &StreamWriter{
		writer: writer,
		config: config,
	}
}

// Write writes data in chunks
func (sw *StreamWriter) Write(data []byte) (int, error) {
	sw.mu.Lock()
	defer sw.mu.Unlock()

	total := 0
	for len(data) > 0 {
		chunkSize := sw.config.ChunkSize
		if len(data) < chunkSize {
			chunkSize = len(data)
		}

		n, err := sw.writer.Write(data[:chunkSize])
		total += n
		sw.bytesWritten += int64(n)
		data = data[n:]

		if err != nil {
			return total, err
		}
	}

	return total, nil
}

// BytesWritten returns total bytes written
func (sw *StreamWriter) BytesWritten() int64 {
	sw.mu.Lock()
	defer sw.mu.Unlock()
	return sw.bytesWritten
}

// LimitedBuffer is a buffer with size limits
type LimitedBuffer struct {
	data     []byte
	maxSize  int
	position int
	mu       sync.RWMutex
}

// NewLimitedBuffer creates a new limited buffer
func NewLimitedBuffer(maxSize int) *LimitedBuffer {
	return &LimitedBuffer{
		data:    make([]byte, 0, minInt(maxSize, 4096)),
		maxSize: maxSize,
	}
}

// Write writes data to the buffer
func (lb *LimitedBuffer) Write(p []byte) (int, error) {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	remaining := lb.maxSize - len(lb.data)
	if remaining <= 0 {
		return 0, io.ErrShortWrite
	}

	toWrite := len(p)
	if toWrite > remaining {
		toWrite = remaining
	}

	lb.data = append(lb.data, p[:toWrite]...)
	return toWrite, nil
}

// Read reads data from the buffer
func (lb *LimitedBuffer) Read(p []byte) (int, error) {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	if lb.position >= len(lb.data) {
		return 0, io.EOF
	}

	n := copy(p, lb.data[lb.position:])
	lb.position += n
	return n, nil
}

// Bytes returns the buffer contents
func (lb *LimitedBuffer) Bytes() []byte {
	lb.mu.RLock()
	defer lb.mu.RUnlock()
	return lb.data
}

// Len returns the buffer length
func (lb *LimitedBuffer) Len() int {
	lb.mu.RLock()
	defer lb.mu.RUnlock()
	return len(lb.data)
}

// Reset resets the buffer
func (lb *LimitedBuffer) Reset() {
	lb.mu.Lock()
	defer lb.mu.Unlock()
	lb.data = lb.data[:0]
	lb.position = 0
}

// IsFull returns true if the buffer is full
func (lb *LimitedBuffer) IsFull() bool {
	lb.mu.RLock()
	defer lb.mu.RUnlock()
	return len(lb.data) >= lb.maxSize
}

// RingBuffer is a circular buffer for streaming data
type RingBuffer struct {
	data  []byte
	size  int
	head  int
	tail  int
	count int
	mu    sync.RWMutex
}

// NewRingBuffer creates a new ring buffer
func NewRingBuffer(size int) *RingBuffer {
	return &RingBuffer{
		data: make([]byte, size),
		size: size,
	}
}

// Write writes data to the ring buffer
func (rb *RingBuffer) Write(p []byte) (int, error) {
	rb.mu.Lock()
	defer rb.mu.Unlock()

	written := 0
	for _, b := range p {
		if rb.count >= rb.size {
			// Buffer full, overwrite oldest
			rb.head = (rb.head + 1) % rb.size
		} else {
			rb.count++
		}

		rb.data[rb.tail] = b
		rb.tail = (rb.tail + 1) % rb.size
		written++
	}

	return written, nil
}

// Read reads data from the ring buffer
func (rb *RingBuffer) Read(p []byte) (int, error) {
	rb.mu.Lock()
	defer rb.mu.Unlock()

	if rb.count == 0 {
		return 0, io.EOF
	}

	n := 0
	for n < len(p) && rb.count > 0 {
		p[n] = rb.data[rb.head]
		rb.head = (rb.head + 1) % rb.size
		rb.count--
		n++
	}

	return n, nil
}

// Len returns the number of bytes in the buffer
func (rb *RingBuffer) Len() int {
	rb.mu.RLock()
	defer rb.mu.RUnlock()
	return rb.count
}

// Cap returns the buffer capacity
func (rb *RingBuffer) Cap() int {
	return rb.size
}

// Reset clears the buffer
func (rb *RingBuffer) Reset() {
	rb.mu.Lock()
	defer rb.mu.Unlock()
	rb.head = 0
	rb.tail = 0
	rb.count = 0
}

// minInt returns the minimum of two integers
func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
