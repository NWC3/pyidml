import mongoengine
import numpy
from pyidml.fields import *
import sys

class XMLSerializableMixin(object):
    @classmethod
    def from_xml(cls, e):
        """
        Returns an instance of this class for the given XML element.
        """
        data = {}
        subclass_tags = Element._get_subclass_tags()
        
        for attr, value in e.items():
            # TODO: A KeyError may want to be supressed here for production
            try:
                data[attr] = cls._fields[attr].to_python(value)
            except:
                exc_class, exc, tb = sys.exc_info()
                new_exc = Exception('%s (%s in %s)'
                                    % (exc or exc_class, attr, cls))
                raise exc_class, new_exc, tb
            
            
        for child in e:
            # If we have specifically defined a field for this child element, 
            # use that
            if child.tag in cls._fields:
                data[child.tag] = cls._fields[child.tag].to_python(child)
            # Otherwise, try to magically add it to self.children by finding 
            # the right subclass of Element
            else:
                if child.tag in subclass_tags:
                    if 'children' not in data:
                        data['children'] = []
                    data['children'].append(
                        subclass_tags[child.tag].from_xml(child)
                    )
        
        return cls(**data)
    

class ElementEmbeddedDocumentField(EmbeddedDocumentField):
    """
    Hack for a self-referential EmbeddedDocumentField in a ListField
    """
    def __init__(self, **kwargs):
        super(mongoengine.EmbeddedDocumentField, self).__init__(**kwargs)
    
    @property
    def document(self):
        return Element
    

class ElementMixin(object):
    def get_children(self, name):
        """
        Returns a list of children with of a given element name.
        """
        if not self.children:
            return []
        return filter(lambda c: c.__class__.__name__ == name, self.children)
   
    def get_element(self, name):
        """
        Returns the child with the given element ID.
        """
        if not self.children:
            return None
        for child in self.children:
            if getattr(child, 'Self', None) == name:
                return child

    def get_document(self):
        """
        Get the root element for the current document.
        """
        if self._class_name == 'Document':
            return self
        elif getattr(self, '_parent', None) is not None:
            return self._parent.get_document()
    
    def get_transformation(self):
        """
        Returns the transformation matrix for this element
        """
        if not getattr(self, 'ItemTransform', None):
            return None
        return numpy.matrix([
            [self.ItemTransform[0], self.ItemTransform[1], 0],
            [self.ItemTransform[2], self.ItemTransform[3], 0],
            [self.ItemTransform[4], self.ItemTransform[5], 1],
        ])

    def get_closest(self, name):
        """
        Returns the nearest ancestor of a given name, including this element.
        """
        if self.__class__.__name__ == name:
            return self
        elif hasattr(self, '_parent') and self._parent:
            return self._parent.get_closest(name)

    def get_relative_transformation(self, element=None):
        """
        Returns the transform matrix for this element relative an element
        given, or by default, the pasteboard.
        """
        if self == element:
            return numpy.identity(3)
        
        transformation = self.get_transformation()
        if transformation is None:
            transformation = numpy.identity(3)
        if hasattr(self, '_parent') and self._parent:
            return transformation * self._parent.get_relative_transformation(element)
        else:
            return transformation



class Element(mongoengine.EmbeddedDocument, XMLSerializableMixin, ElementMixin):
    children = ListField(ElementEmbeddedDocumentField())
    
    @classmethod
    def _get_subclasses(cls):
        try:
            return cls._subclasses
        except AttributeError:
            cls._subclasses = super(Element, cls)._get_subclasses()
            return cls._subclasses
    
    @classmethod
    def _get_subclass_tags(cls):
        try:
            return cls._subclass_tags
        except AttributeError:
            cls._subclass_tags = dict([
                (k.split('.')[-1], v)
                for k, v in cls._get_subclasses().items()
            ])
            return cls._subclass_tags
        
    def __eq__(self, other):
        if super(Element, self).__eq__(other):
            return True
        # Elements are equal if they are from the same document and have the
        # same object ID
        if isinstance(other, self.__class__):
            this_doc = self.get_document()
            other_doc = other.get_document()
            if this_doc and other_doc and this_doc == other_doc:
                if hasattr(self, 'Self') and hasattr(other, 'Self'):
                    return self.Self == other.Self
        return False


class Properties(Element):
    Label = KeyValuePairField()
    

