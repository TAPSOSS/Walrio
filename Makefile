MAKEFLAGS = --warn-undefined-variables
# make sort behave sanely
export LC_ALL=C

#@ help - Show this messsage
#@
help:
	@egrep "^#@" ${MAKEFILE_LIST} | cut -c 3-



#@ check_style - Run style checker on all py files
#@
check_style:
	python3 .github/scripts/enhanced_style_checker.py modules/*py modules/*/*py



#@ gen_doc - Extract documentation from py files
#@
check_style: