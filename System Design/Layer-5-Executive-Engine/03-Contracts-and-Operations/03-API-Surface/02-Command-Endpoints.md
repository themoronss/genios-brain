# Command endpoints

Commands cover action completion, guarded state transition, dismissal, reassignment and an
owner-only sweep trigger. Bodies are typed and handlers delegate to the store/unit authority.

A client cannot mark an action complete out of dependency order or transition a terminal
commitment through an illegal edge.
