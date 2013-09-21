#!/usr/bin/env python


def main():
    tailleFixe = 80
    ficEntree = '<HERE-INPUT-FILE-PATH>'
    ficSortie = '<HERE-OUTPUT-FILE-PATH>'

    numLigne = 0
    with open(ficEntree, "r") as fEntree, \
            open(ficSortie, "w") as fSortie:

        for line in fEntree:
            lineIn = line.rstrip('\r\n')

            numLigne = numLigne + 1
            taille = len(lineIn)
            if taille < tailleFixe:
                nbBlanks = tailleFixe - taille
                print "blanks added, old: %s - added: %s" % (taille, nbBlanks)
                strBlanks = " " * nbBlanks
                fSortie.write(lineIn + strBlanks + "\n")
            elif taille > tailleFixe:
                print "current width > fixed width, at line %s" % numLigne


if __name__ == '__main__':
    main()
