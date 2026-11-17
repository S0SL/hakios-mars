/*
 * Minimal persistent process 1 for the Apple-free APFS bootstrap.
 *
 * It deliberately does not use mmap, sysctl, UFS or any optional subsystem:
 * by this point init has already exercised those paths. Keeping PID 1 alive
 * must not depend on any of them.
 */
#include "mini.h"

int
main(int argc, char **argv, char **envp)
{
	int fd = open("/dev/console", O_RDWR, 0);

	(void)argc;
	(void)argv;
	(void)envp;
	if (fd >= 0) {
		dup2(fd, 0);
		dup2(fd, 1);
		dup2(fd, 2);
		if (fd > 2) {
			close(fd);
		}
		printf("HOLD: PID 1 is alive and staying here.\n");
	}

	for (;;) {
		__asm__ volatile ("" ::: "memory");
	}
}
