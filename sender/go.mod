module pale-moon/sender

go 1.24

require (
	golang.org/x/net v0.30.0
	pale-moon/pulse v0.0.0
)

require golang.org/x/sys v0.26.0 // indirect

replace pale-moon/pulse => ../pulse
